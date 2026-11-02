"""Real nginx regression tests; stdlib only. Set NGINX_BIN to a local binary."""
import base64
import hashlib
from html.parser import HTMLParser
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
NGINX = os.environ.get('NGINX_BIN') or shutil.which('nginx')
REQUESTS = []


class Upstream(BaseHTTPRequestHandler):
    def do_GET(self):
        REQUESTS.append((self.path, dict(self.headers)))
        data = json.dumps({'path': self.path}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Set-Cookie', 'upstream_session=must-not-leak')
        self.send_header('X-Powered-By', 'private-backend-version')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class TLSUpstream(ThreadingHTTPServer):
    tls_context: ssl.SSLContext

    def get_request(self):
        connection, address = super().get_request()
        return self.tls_context.wrap_socket(connection, server_side=True), address


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class ContentSecurity(unittest.TestCase):
    def test_blank_links_explicitly_disown_opener(self):
        bad = []
        for path in sorted((ROOT / 'app/template').glob('*.html')):
            parser = Tags()
            parser.feed(path.read_text())
            for tag, attrs in parser.tags:
                if tag == 'a' and attrs.get('target') == '_blank':
                    if 'noopener' not in attrs.get('rel', '').split():
                        bad.append(f'{path.name}: {attrs.get("href")}')
        self.assertEqual(bad, [])

    def test_build_context_and_git_ignore_environment_variants_and_keys(self):
        for name in ('.dockerignore', '.gitignore'):
            patterns = (ROOT / name).read_text().splitlines()
            with self.subTest(file=name):
                for pattern in ['**/.env', '**/.env.*', '**/*.pem', '**/*.key', '**/*.p12', '**/*.pfx']:
                    self.assertIn(pattern, patterns)

    def test_csp_pins_every_inline_script_including_json_ld(self):
        policy = ROOT / 'nginx/security-headers.conf'
        self.assertTrue(policy.exists(), 'Security-header snippet missing')
        config = (ROOT / 'nginx/default.conf').read_text() + policy.read_text() + (ROOT / 'nginx/csp.conf').read_text()
        for path in sorted((ROOT / 'app/template').glob('*.html')):
            for attrs, script in re.findall(r'<script\b([^>]*)>([\s\S]*?)</script>', path.read_text()):
                if 'src=' not in attrs:
                    digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
                    self.assertIn(f"'sha256-{digest}'", config, f'{path.name}: stale CSP hash')
        self.assertNotIn("'unsafe-inline'", config)
        self.assertNotIn("'unsafe-eval'", config)


@unittest.skipUnless(NGINX, 'nginx unavailable; set NGINX_BIN')
class NginxSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='novaroma-nginx-')
        cls.base = Path(cls.tmp.name)
        cls.web = cls.base / 'html'
        shutil.copytree(ROOT / 'app/template', cls.web)
        # Planted test canaries, never real secrets or production content.
        for name in ['.env', '.env.production', '.git/config', 'nested/.env', 'backup.sql', 'key.pem',
                     'test-credential.p12', 'test-credential.pfx']:
            target = cls.web / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('TEST_CANARY_NOT_A_SECRET')
        (cls.web / 'svenja').mkdir(exist_ok=True)
        (cls.web / 'svenja/index.html').write_text('<script>window.legacy=true</script>')
        cls.http = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
        cls.https = TLSUpstream(('127.0.0.1', 0), Upstream)
        key, cert = cls.base / 'key.pem', cls.base / 'cert.pem'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-keyout', str(key), '-out', str(cert), '-days', '1',
                        '-subj', '/CN=api.github.com', '-addext', 'subjectAltName=DNS:api.github.com'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        cls.tls_context = ctx
        cls.https.tls_context = ctx
        for server in (cls.http, cls.https):
            threading.Thread(target=server.serve_forever, daemon=True).start()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            cls.port = sock.getsockname()[1]
        config = (ROOT / 'nginx/default.conf').read_text()
        config = config.replace('listen 8000;', f'listen 127.0.0.1:{cls.port};')
        config = config.replace('/usr/share/nginx/html', str(cls.web))
        config = config.replace('/var/cache/nginx/github_api_cache', str(cls.base / 'cache'))
        config = config.replace('/etc/nginx/snippets/', str(ROOT / 'nginx') + '/')
        config = config.replace('http://api:8080', f'http://127.0.0.1:{cls.http.server_port}')
        config = config.replace('http://svenja-game-v2:5000', f'http://127.0.0.1:{cls.http.server_port}')
        config = config.replace('https://api.github.com', f'https://127.0.0.1:{cls.https.server_port}')
        config = config.replace('/etc/ssl/certs/ca-certificates.crt', str(cert))
        mime = Path(os.environ.get('NGINX_MIME_TYPES', '/etc/nginx/mime.types'))
        mime_line = f'include {mime};' if mime.exists() else 'types { text/html html; text/css css; application/javascript js; }'
        cls.conf = cls.base / 'nginx.conf'
        cls.conf.write_text(f'master_process off;\npid {cls.base}/nginx.pid;\nerror_log {cls.base}/error.log;\n'
                            f'events {{}}\nhttp {{ access_log off; {mime_line}\n'
                            f'client_body_temp_path {cls.base}/body; proxy_temp_path {cls.base}/proxy;\n'
                            f'fastcgi_temp_path {cls.base}/fastcgi; uwsgi_temp_path {cls.base}/uwsgi;\n'
                            f'scgi_temp_path {cls.base}/scgi;\n{config}\n}}\n')
        cls.args = [NGINX, '-p', str(cls.base) + '/', '-c', str(cls.conf)]
        result = subprocess.run(cls.args + ['-t'], capture_output=True, text=True)
        print(result.stderr.strip(), flush=True)
        if result.returncode:
            raise RuntimeError(result.stderr)
        subprocess.run(cls.args, check=True)

    @classmethod
    def tearDownClass(cls):
        subprocess.run(cls.args + ['-s', 'quit'], check=True)
        for server in (cls.http, cls.https):
            server.shutdown()
            server.server_close()
        cls.tmp.cleanup()

    def request(self, path, method='GET', headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        conn.request(method, path, headers=headers or {})
        res = conn.getresponse()
        answer = res.status, dict((k.lower(), v) for k, v in res.getheaders()), res.read()
        conn.close()
        return answer

    def test_security_headers_survive_locations_errors_redirects_and_304(self):
        for path in ['/', '/health', '/llms.txt', '/favicon.ico', '/assets/nova-roma-logo.png',
                     '/api/check-health', '/missing', '/svenja', '/svenja/bibliothek/library/covers/test.png']:
            with self.subTest(path=path):
                _, headers, _ = self.request(path)
                self.assertEqual(headers.get('x-content-type-options'), 'nosniff')
                self.assertEqual(headers.get('x-frame-options'), 'SAMEORIGIN')
                self.assertEqual(headers.get('referrer-policy'), 'strict-origin-when-cross-origin')
                self.assertNotIn('nginx/', headers.get('server', ''))
                self.assertNotIn('x-powered-by', headers)
        _, headers, _ = self.request('/index.html')
        status, cached_headers, _ = self.request('/index.html', headers={'If-None-Match': headers['etag']})
        self.assertEqual(status, 304)
        self.assertIn('content-security-policy', cached_headers)

    def test_csp_enforced_without_changing_unknown_svenja_policy(self):
        for path in ['/', '/Activity.html', '/404.html', '/missing']:
            _, headers, _ = self.request(path)
            policy = headers.get('content-security-policy', '')
            self.assertIn("default-src 'self'", policy)
            self.assertIn("object-src 'none'", policy)
            self.assertIn("base-uri 'none'", policy)
            self.assertIn("frame-ancestors 'self'", policy)
            self.assertNotIn("'unsafe-inline'", policy)
        _, headers, _ = self.request('/svenja/')
        self.assertNotIn('content-security-policy', headers)

    def test_github_proxy_strips_credentials_and_upstream_cookie(self):
        REQUESTS.clear()
        status, headers, body = self.request('/github/repos/JestingDart4369/Python_Panel/commits?per_page=3',
                    headers={'Authorization': 'Bearer TEST_CANARY', 'Cookie': 'private=TEST_CANARY',
                             'X-Canary': 'not-for-github'})
        self.assertEqual(status, 200, body)
        self.assertEqual(len(REQUESTS), 1)
        path, forwarded = REQUESTS[0]
        self.assertEqual(path, '/repos/JestingDart4369/Python_Panel/commits?per_page=3')
        self.assertFalse({'authorization', 'cookie', 'x-canary'} & {k.lower() for k in forwarded})
        self.assertNotIn('set-cookie', headers)
        self.assertNotIn('x-powered-by', headers)
        self.assertEqual(headers.get('x-content-type-options'), 'nosniff')
        _, cached_headers, _ = self.request('/github/repos/JestingDart4369/Python_Panel/commits?per_page=3',
                                          headers={'Cookie': 'other=TEST_CANARY'})
        self.assertEqual(cached_headers.get('x-proxy-cache'), 'HIT')
        self.assertEqual(len(REQUESTS), 1)
        self.assertNotIn('set-cookie', cached_headers)
        self.assertEqual(cached_headers.get('x-content-type-options'), 'nosniff')

    def test_github_proxy_rejects_non_public_routes_and_write_methods(self):
        for path in ['/github/user', '/github/repos/other/private/commits',
                     '/github/repos/JestingDart4369/Python_Panel/issues']:
            with self.subTest(path=path):
                status, _, _ = self.request(path)
                self.assertEqual(status, 404)
        status, _, _ = self.request('/github/repos/JestingDart4369/Python_Panel/commits', method='POST')
        self.assertIn(status, (403, 405))

    def test_github_upstream_tls_is_verified(self):
        config = (ROOT / 'nginx/default.conf').read_text()
        self.assertIn('proxy_ssl_verify on;', config)
        self.assertIn('proxy_ssl_name api.github.com;', config)
        self.assertIn('proxy_ssl_trusted_certificate /etc/ssl/certs/ca-certificates.crt;', config)

    def test_github_untrusted_tls_certificate_is_rejected(self):
        bad_key, bad_cert = self.base / 'bad-key.pem', self.base / 'bad-cert.pem'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-keyout', str(bad_key), '-out', str(bad_cert), '-days', '1',
                        '-subj', '/CN=untrusted.invalid'], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Swap the whole server context: reusing it could resume an already-verified TLS session.
        bad_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        bad_context.load_cert_chain(bad_cert, bad_key)
        self.https.tls_context = bad_context
        try:
            status, headers, _ = self.request('/github/repos/JestingDart4369/Python_Panel/commits?tls-negative=1')
            self.assertEqual(status, 502)
            self.assertEqual(headers.get('x-content-type-options'), 'nosniff')
        finally:
            self.https.tls_context = self.tls_context

    def test_sensitive_files_never_served_even_if_accidentally_copied(self):
        for path in ['/.env', '/.env.production', '/.git/config', '/nested/.env', '/backup.sql', '/key.pem',
                     '/test-credential.p12', '/test-credential.pfx', '/%2eenv', '/assets/../.env']:
            with self.subTest(path=path):
                status, _, body = self.request(path)
                self.assertIn(status, (403, 404))
                self.assertNotIn(b'TEST_CANARY_NOT_A_SECRET', body)


if __name__ == '__main__':
    unittest.main(verbosity=2)
