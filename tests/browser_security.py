"""Optional real Chromium smoke/security checks against the same local nginx harness.
Install playwright in a project-local venv; no production service is contacted.
"""
import json
from pathlib import Path
import sys
import subprocess

sys.path.insert(0, str(Path(__file__).parent))
from test_security import NginxSecurity
from playwright.sync_api import sync_playwright

PAGES = ['index.html', 'portfolio.html', 'Projects.html', 'Activity.html', 'Services.html', 'missing']


def main():
    NginxSecurity.setUpClass()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            context = browser.new_context(viewport={'width': 1200, 'height': 900})
            origin = f'http://127.0.0.1:{NginxSecurity.port}'
            # Map absolute production-branding image URLs to the local clone, not the network.
            context.route('https://novaroma-homelab.uk/assets/**',
                          lambda route: route.fulfill(path=str(NginxSecurity.web / ('assets/' + route.request.url.split('/assets/')[1].split('?')[0]))))
            context.route('https://github.com/**', lambda route: route.abort())
            context.route('**/api/check-health', lambda route: route.fulfill(status=200, content_type='application/json', body='{}'))
            malicious = '<img src=x onerror="window.__xss=true"> & literal markup'
            payload = {'message': 'Security audit smoke commit'}
            context.route('**/github/repos/**', lambda route: route.fulfill(status=200, content_type='application/json', body=json.dumps([{'commit': {'message': payload['message']}}])))
            for name in PAGES:
                page = context.new_page()
                page.add_init_script("window.__violations=[]; document.addEventListener('securitypolicyviolation', e => window.__violations.push(e.effectiveDirective + ':' + e.blockedURI));")
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(f'{origin}/{name}', wait_until='networkidle')
                assert not errors, (name, errors)
                assert not page.evaluate('window.__violations.length'), (name, page.evaluate('window.__violations'))
                assert page.locator('header img').evaluate('(img) => img.complete && img.naturalWidth > 0'), name
                assert page.locator('body').evaluate('(el) => getComputedStyle(el).backgroundColor') != 'rgba(0, 0, 0, 0)', name
                # Pixel comparison against the original tracked HTML with identical fixtures.
                baseline = context.new_page()
                source_name = '404.html' if name == 'missing' else name
                original = subprocess.check_output(['git', 'show', f'HEAD:app/template/{source_name}'], cwd=Path(__file__).resolve().parents[1])
                baseline.route(f'{origin}/{name}', lambda route: route.fulfill(status=404 if name == 'missing' else 200, content_type='text/html', body=original))
                baseline.goto(f'{origin}/{name}', wait_until='networkidle')
                assert baseline.screenshot(full_page=True) == page.screenshot(full_page=True), f'{name}: appearance changed'
                baseline.close()
                if name != 'missing':
                    page.set_viewport_size({'width': 390, 'height': 844})
                    page.locator('#menu-btn').click()
                    assert 'open' in page.locator('#nav-links').get_attribute('class'), name
                    page.locator('#menu-btn').click()
                    page.set_viewport_size({'width': 1200, 'height': 900})
                if name in ('index.html', 'Services.html'):
                    assert page.locator('#api-status').inner_text() == 'Online — API responding: 200'
                if name == 'Activity.html':
                    payload['message'] = malicious + '\nsecond line'
                    page.reload(wait_until='networkidle')
                    assert page.locator('.commit-msg').count() == 3
                    assert page.locator('.commit-msg').first.inner_text() == malicious
                    assert page.locator('.commit-msg img').count() == 0
                    assert page.evaluate('window.__xss === undefined')
                # Exercise both the dynamic inline style used for accessibility and canvas FX.
                footer = page.locator('footer p')
                for _ in range(5):
                    footer.dispatch_event('click')
                assert page.locator('html').get_attribute('data-season')
                assert page.locator('#season-fx').count() == 1
                assert not page.evaluate('window.__violations.length'), (name, page.evaluate('window.__violations'))
                # Ensure an injected *unhashed* inline script is actually blocked by the browser.
                page.evaluate("() => { const s=document.createElement('script'); s.textContent='window.__injected=true'; document.body.append(s); }")
                assert page.evaluate('window.__injected === undefined'), name
                assert any(v.startswith('script-src-elem:inline') for v in page.evaluate('window.__violations')), name
                payload['message'] = 'Security audit smoke commit'
                context.clear_cookies()
                page.close()
                print(f'PASS {name}: pixel-identical baseline, assets/CSS, interactions, seasons, CSP enforcement', flush=True)
            browser.close()
    finally:
        NginxSecurity.tearDownClass()


if __name__ == '__main__':
    main()
