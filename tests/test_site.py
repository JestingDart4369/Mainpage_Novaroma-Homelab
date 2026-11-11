"""Static-hosting checks: no inline scripts, CSP meta present, commits snapshot builder."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import fetch_commits  # noqa: E402

PAGES = sorted((ROOT / 'app/template').glob('*.html'))


class StaticSite(unittest.TestCase):
    def test_no_inline_executable_scripts(self):
        for path in PAGES:
            for attrs, body in re.findall(r'<script\b([^>]*)>([\s\S]*?)</script>', path.read_text()):
                if 'src=' not in attrs:
                    self.assertIn('ld+json', attrs, f'{path.name}: inline script would violate script-src self')

    def test_every_page_ships_the_same_csp_meta(self):
        policies = set()
        for path in PAGES:
            match = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)"', path.read_text())
            self.assertTrue(match, f'{path.name}: CSP meta missing')
            policies.add(match.group(1))
        self.assertEqual(len(policies), 1)
        self.assertNotIn('unsafe', next(iter(policies)))

    def test_status_check_calls_the_api_origin_allowed_by_csp(self):
        script = (ROOT / 'app/template/site.js').read_text()
        self.assertIn('https://api.novaroma-homelab.uk/health', script)
        self.assertIn('connect-src', (ROOT / 'nginx/csp.conf').read_text())
        self.assertIn('https://api.novaroma-homelab.uk', (ROOT / 'nginx/csp.conf').read_text())


class CommitSnapshot(unittest.TestCase):
    def test_simplify_keeps_only_first_line_and_date(self):
        payload = [{'commit': {'message': 'Title\n\nbody with secrets?', 'committer': {'date': '2026-11-01T10:00:00Z'},
                               'author': {'email': 'private@example.com'}}, 'sha': 'abc'}]
        self.assertEqual(fetch_commits.simplify('o/r', payload),
                         [{'repo': 'o/r', 'message': 'Title', 'when': '2026-11-01T10:00:00Z'}])

    def test_build_sorts_newest_first_and_records_failures(self):
        def fake(repo, token):
            if repo == 'o/bad':
                raise OSError('boom')
            return [{'repo': repo, 'message': 'm', 'when': {'o/a': '2026-01-01', 'o/b': '2026-02-01'}[repo]}]
        result = fetch_commits.build(['o/a', 'o/bad', 'o/b'], fetch=fake)
        self.assertEqual([c['repo'] for c in result['commits']], ['o/b', 'o/a'])
        self.assertEqual(result['failed'], ['o/bad'])

    def test_token_is_never_written_to_the_snapshot(self):
        result = fetch_commits.build(['o/a'], token='ghs_secret',
                                     fetch=lambda repo, token: [{'repo': repo, 'message': 'm', 'when': 'x'}])
        self.assertNotIn('ghs_secret', json.dumps(result))


if __name__ == '__main__':
    unittest.main()
