#!/usr/bin/env python3
"""Regenerate every data-driven part of the site from app/template/site-data.json.

    python3 scripts/sync_site.py          # rewrite files
    python3 scripts/sync_site.py --check  # exit 1 if anything is out of sync (used by tests)

site-data.json is the single source of truth for the tech stack, the project cards,
the Activity repo tabs and the nginx allowlist of public commit feeds.
"""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'app/template'
DATA = json.loads((TEMPLATE / 'site-data.json').read_text(encoding='utf-8'))
E = html.escape


def stack_html(indent):
    pad = ' ' * indent
    lines = []
    for item in DATA['stack']:
        if item.get('icon'):
            lines.append(f'{pad}<img src="{E(item["icon"])}" alt="{E(item["name"])} logo" class="tag-icon" '
                         f'width="{item["width"]}" height="{item["height"]}">')
        else:
            lines.append(f'{pad}<span class="tag">{E(item["name"])}</span>')
    return '\n'.join(lines)


def repo_url(repo):
    return f'https://github.com/{repo["owner"]}/{repo["name"]}'


def card_html():
    out = []
    for repo in DATA['repos']:
        links = ''.join(
            f'            <a href="{E(link.get("url") or repo_url(repo))}" target="_blank" rel="noopener" '
            f'class="btn-secondary">{E(link["label"])}</a>\n' for link in repo['links'])
        tags = ''.join(f'            <span class="card-tag">{E(t)}</span>\n' for t in repo['tags'])
        out.append(
            '          <div class="project-card">\n' + tags +
            f'            <h3>{E(repo["title"])}</h3>\n'
            f'            <p>{E(repo["description"])}</p>\n'
            '            <p class="card-stats">⭐ — stars &nbsp; ⑂ — forks &nbsp; ⚑ — issues</p>\n' +
            links + '          </div>\n')
    p = DATA['profile']
    tags = ''.join(f'            <span class="card-tag">{E(t)}</span>\n' for t in p['tags'])
    out.append(
        '          <div class="project-card">\n' + tags +
        f'            <h3>{E(p["title"])}</h3>\n'
        f'            <p>{E(p["description"])}</p>\n'
        '            <p class="card-stats">⭐ — total stars &nbsp; ⑂ — total forks</p>\n'
        f'            <a href="{E(p["url"])}" target="_blank" rel="noopener" class="btn-secondary">{E(p["label"])}</a>\n'
        '          </div>\n')
    return '\n'.join(out)


def tabs_html():
    return '\n'.join(f'          <span class="repo-tab">{E(r["tabLabel"])}</span>' for r in DATA['repos'])


def nginx_regex():
    owners = {}
    for r in DATA['repos']:
        owners.setdefault(r['owner'], []).append(re.escape(r['name']).replace('\\-', '-'))
    parts = [f'{o}/({"|".join(names)})' if len(names) > 1 else f'{o}/{names[0]}' for o, names in owners.items()]
    return f'    location ~ ^/github/repos/({"|".join(parts)})/commits$ {{'


def between(text, start, end, body):
    pattern = re.compile(re.escape(start) + r'.*?' + re.escape(end), re.S)
    if not pattern.search(text):
        raise SystemExit(f'marker not found: {start}')
    return pattern.sub(lambda _: f'{start}\n{body}\n{end}', text, count=1)


def render():
    files = {}
    for path in sorted(TEMPLATE.glob('*.html')):
        text = path.read_text(encoding='utf-8')
        new = re.sub(r'(<div class="tags" data-sync="stack">)\n.*?\n(\s*</div>)',
                     lambda m: f'{m.group(1)}\n{stack_html(12)}\n{m.group(2)}', text, flags=re.S)
        if path.name == 'Projects.html':
            new = between(new, '<!-- sync:projects:start -->', '<!-- sync:projects:end -->', card_html().rstrip('\n'))
        if path.name == 'Activity.html':
            new = between(new, '<!-- sync:repo-tabs:start -->', '<!-- sync:repo-tabs:end -->', tabs_html())
        files[path] = new
    conf = ROOT / 'nginx/default.conf'
    text = conf.read_text(encoding='utf-8')
    files[conf] = re.sub(r'    location ~ \^/github/repos/.*?commits\$ \{', lambda _: nginx_regex(), text, count=1)
    return files


def main():
    changed = []
    for path, new in render().items():
        if path.read_text(encoding='utf-8') != new:
            changed.append(str(path.relative_to(ROOT)))
            if '--check' not in sys.argv:
                path.write_text(new, encoding='utf-8')
    if changed and '--check' in sys.argv:
        print('out of sync with site-data.json (run scripts/sync_site.py):', *changed, sep='\n  ')
        return 1
    print('updated:' if changed else 'already in sync', *changed)
    return 0


if __name__ == '__main__':
    sys.exit(main())
