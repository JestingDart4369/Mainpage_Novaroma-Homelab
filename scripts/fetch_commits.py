#!/usr/bin/env python3
"""Write commits.json: the latest commits of every repo in site-data.json.

    python3 scripts/fetch_commits.py OUTPUT.json

Used by the GitHub Pages workflow so the static site needs no server-side proxy.
GITHUB_TOKEN (optional) raises the API rate limit; it is only sent to api.github.com
and never written to the output.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PER_REPO = 3


def simplify(repo, payload):
    """Reduce a GitHub commits response to the few fields the Activity page shows."""
    out = []
    for item in payload:
        commit = item['commit']
        when = (commit.get('committer') or commit.get('author') or {}).get('date', '')
        out.append({'repo': repo, 'message': commit['message'].split('\n')[0], 'when': when})
    return out


def fetch_repo(repo, token=None):
    request = urllib.request.Request(
        f'https://api.github.com/repos/{repo}/commits?per_page={PER_REPO}',
        headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'novaroma-mainpage'})
    if token:
        request.add_header('Authorization', f'Bearer {token}')
    with urllib.request.urlopen(request, timeout=20) as response:
        return simplify(repo, json.load(response))


def build(repos, token=None, fetch=fetch_repo):
    commits, failed = [], []
    for repo in repos:
        try:
            commits.extend(fetch(repo, token))
        except Exception:
            failed.append(repo)
    commits.sort(key=lambda c: c['when'], reverse=True)
    return {'generated': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'commits': commits, 'failed': failed}


def main():
    data = json.loads((ROOT / 'app/template/site-data.json').read_text(encoding='utf-8'))
    repos = [f'{r["owner"]}/{r["name"]}' for r in data['repos']]
    result = build(repos, os.environ.get('GITHUB_TOKEN'))
    if not result['commits']:
        print('no commits fetched; refusing to publish an empty snapshot', file=sys.stderr)
        return 1
    Path(sys.argv[1]).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'wrote {len(result["commits"])} commits, {len(result["failed"])} repo(s) failed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
