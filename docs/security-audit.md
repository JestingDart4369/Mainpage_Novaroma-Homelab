# Website security audit and hardening

## Scope and delivery state

- Reviewed the local `Mainpage_Novaroma-Homelab` clone at baseline `657647df2a716137efe87ff646e4e3f6ab091334`.
- Work is on `fix/security-headers`, **uncommitted, unpushed and undeployed** for independent review.
- Inspected tracked nginx configuration, Dockerfile/Compose/build exclusions, HTML, JavaScript, CSS and public assets. No production machine or production secret was accessed. The separate API authentication/salt/pepper work is out of scope.
- Production-only untracked `app/template/svenja/` was not read, created, deleted or edited. Its existing nginx routes are retained. A synthetic Svenja fixture exists only inside disposable test directories.

## Findings and changes

| Finding | Evidence before changes | Resolution |
| --- | --- | --- |
| High: DOM XSS through external commit messages | Activity interpolated `c.commit.message` into `innerHTML`; the regression test showed injected image/script markup reaching the HTML sink. Exploitation requires control of commit text returned for one of the configured repositories. | Build the same `.commit-item`, `.commit-repo` and `.commit-msg` elements with `createElement` and `textContent`. Preserve first-line display and failure text. No content or stylesheet changes. |
| High: website credentials forwarded to GitHub | A real nginx request with test Authorization, Cookie and arbitrary headers was observed at the local HTTPS upstream. | Disable original request headers/body on the GitHub proxy, set only public API headers, strip upstream cookies and X-Powered-By. The shared cached response is now independent of browser credentials; a second request is verified as a cache HIT without cookies. No real private-data cache exposure was investigated or claimed. |
| Medium: unnecessarily broad GitHub proxy | `/github/user`, other repositories and write methods reached the mock upstream. | Allow only GET/HEAD for the three existing public commit-feed paths; return 404 for other GitHub routes and reject write methods. Existing UI requests remain unchanged. |
| Medium: GitHub upstream certificate not verified | `proxy_ssl_server_name on` was present, but certificate verification was not enabled. | Enable certificate verification with explicit GitHub hostname, CA bundle and chain depth. Local trusted TLS succeeds; an untrusted certificate produces 502. |
| Medium: no CSP or anti-framing/MIME headers | Live local nginx regression requests lacked these headers across static, proxy, error and redirect routes. | Add enforced hash-based CSP, nosniff, SAMEORIGIN and strict-origin-when-cross-origin referrer policy. Use `always` and repeat the shared snippet wherever location-level `add_header` would suppress inheritance. Verified on 200, 301, 304, 404 and upstream 502 responses. |
| Defense in depth: accidental secret publication | Synthetic `.env`, `.env.production`, `.git/config`, nested/encoded dotfiles, `.sql` and `.pem` canaries were served with 200 before the fix. This is not evidence that real secrets were published. | Deny hidden files (except `.well-known`), key/database/backup suffixes; exclude nested environment variants and common private-key/certificate containers from Git and Docker context. |
| Low: missing explicit opener isolation | Five new-tab links in Projects/Services lacked `rel="noopener"`. | Add `noopener` to those five links; retain hrefs, labels and appearance. Modern browsers may already imply it, but explicit coverage also protects older clients. |
| Low: version disclosure | Local responses exposed `nginx/<version>`; mock backend exposed X-Powered-By. | Disable nginx version tokens and hide backend X-Powered-By. The generic `Server: nginx` product header remains. |

## CSP compatibility and boundaries

`nginx/csp.conf` contains the policy map. `nginx/security-headers.conf` is included at server scope and in every location that declares its own headers. Docker copies both snippets to `/etc/nginx/snippets/`.

- Inline executable scripts and JSON-LD remain in the documents, with SHA-256 hashes covering their exact contents and whitespace. There is no `unsafe-inline`, `unsafe-eval`, wildcard script host, or inline event-handler allowance.
- `seasons.js`, both stylesheets and ordinary images are self-hosted. Absolute branding image URLs also allow the canonical HTTPS site. GitHub preconnect is accounted for in `connect-src`; API status and GitHub data fetches are same-origin. External navigational links do not require script permission.
- Seasonal canvas effects, the accessibility live region's JavaScript-applied style, cookie persistence and menu interactions work under the enforced policy in Chromium.
- `/svenja` and `/svenja/...` intentionally receive **no new CSP**: their untracked assets/scripts could not safely be inventoried. Other common headers and sensitive-file guards apply to the server. An internal redirect to the main site's 404 document correctly receives the mainpage policy.
- Existing upstream CSP, if any, is not stripped. The API and Svenja application behavior/authentication is not audited here.
- Any future inline-script or JSON-LD edit must update the hashes atomically with the HTML. Run the hash test before building; it reports stale hashes. To calculate the required values without changing files:

```bash
python - <<'PY'
import base64, hashlib, re
from pathlib import Path
for path in sorted(Path('app/template').glob('*.html')):
    for attrs, body in re.findall(r'<script\b([^>]*)>([\s\S]*?)</script>', path.read_text()):
        if 'src=' not in attrs:
            digest = base64.b64encode(hashlib.sha256(body.encode()).digest()).decode()
            print(path.name, "'sha256-" + digest + "'")
PY
```

Replace the script hash list in `nginx/csp.conf` with the deduplicated current values, retaining all other directives. Do not relax the policy to work around a missed hash.

## Verification performed

Exact final command output is retained in `docs/security-verification.txt`.

1. Python unittest: **10 tests passed, no skips**, including real nginx routing/proxy/cache/header/secret-canary requests and positive/negative TLS.
2. Node test runner: **2 tests passed, 0 failed** against the actual Activity inline script, covering malicious commit text and request failure fallback.
3. Chromium: **6 pages passed**: index, portfolio, Projects, Activity, Services and a missing page. Full-page PNG screenshots were byte-identical to original HEAD HTML under identical harmless API fixtures at 1200px width. Mobile-menu clicks were tested at 390px width. Assets/CSS, status, commit text, season toggling/canvas and blocking a deliberately injected unhashed script were exercised. Initial page loads and legitimate interactions produced no CSP violations.
4. HTML outside script bodies and added `rel` attributes is unchanged; CSS/image changes: **none**.
5. Heuristic scan of **21 tracked text files** found no private-key markers, recognized GitHub/AWS credential formats or quoted password/secret/token assignments; no tracked sensitive-path candidates. This is not a comprehensive historical secret audit.
6. `git diff --check`: passed.

The new regression cases were run red before their corresponding fixes: Activity injection/fallback, missing security headers/CSP, proxy credential forwarding/route/method/TLS configuration, exposed synthetic files, missing noopener and insufficient ignore rules. Later TLS-negative and cache-HIT cases extend the same behavior coverage.

### Independent-review correction: PKCS#12 suffixes

The independent review found that the nginx sensitive-file deny regex omitted `.p12` and `.pfx`, despite both suffixes already being excluded by Git/Docker ignore rules. Added disposable `test-credential.p12` and `test-credential.pfx` canaries to the existing integration regression first: both requests returned **200**, producing two failing subtests. Added only `p12|pfx` to the case-insensitive suffix deny regex. The complete Python suite then passed **10 tests, no skips**, including both canaries being denied without leaking their content; Node passed **2 tests**, and `git diff --check` passed. Exact commands/output are appended to `security-verification.txt`. Previous browser results above were not rerun for this suffix-only correction. No production, secrets, commits, pushes or deployments were touched.

### Local reproduction

Requirements: Python 3, Node with its built-in test runner, OpenSSL and nginx. The base suite needs no Python packages. Set `TMPDIR` to a private scratch directory if the shell does not already do so.

```bash
node --test tests/activity-security.test.js
NGINX_BIN=/path/to/nginx python -m unittest discover -s tests -p test_security.py -v
```

Without nginx the integration class explicitly skips; **a skipped run is not equivalent to this verification**. Tests rewrite only local listen/root/cache/include/upstream/CA paths and use temporary loopback HTTP/HTTPS upstreams. Production is never contacted. The harness invokes `nginx -t` before starting a disposable server.

The audit host had no Docker/nginx installed. A Debian nginx package was downloaded and extracted into `/home/hermes/.hermes/cache/scratch/novaroma-security-tools/`, without system installation. Actual test executable: `root/usr/sbin/nginx`, version **1.26.3**. All directives used are also compatible with the repository's 1.27 configuration syntax, but the actual Alpine image still requires validation.

Optional browser reproduction, installed only in a scratch/local venv during this audit:

```bash
python -m venv /path/to/local-test-venv
/path/to/local-test-venv/bin/python -m pip install playwright
PLAYWRIGHT_BROWSERS_PATH=/path/to/local-browsers /path/to/local-test-venv/bin/python -m playwright install chromium
NGINX_BIN=/path/to/nginx PLAYWRIGHT_BROWSERS_PATH=/path/to/local-browsers /path/to/local-test-venv/bin/python tests/browser_security.py
```

The appearance comparison uses `git show HEAD:app/template/<page>` as the baseline, so before committing this compares against the original code; after committing, use a preserved pre-change worktree if an independent old/new comparison is required. Network/API responses in browser checks are explicit test fixtures, not claimed live GitHub/API results.

## Deployment instructions — operator action only, not performed

1. Independently review this branch, test and commit/push using the existing repository workflow. Save the previous image identifier for rollback.
2. Apply the reviewed tracked changes to the **existing production deployment tree**. Preserve and back up untracked `app/template/svenja/` using the operator's existing backup process. Do not run `git clean`, destructive reset, replace the whole tree with this clean clone, or deploy an image lacking those production-only assets. Keep all production secret files outside the web root/build context.
3. Use the **existing production Compose project/network**, not this repository's standalone Compose file blindly. Startup validation needs the existing `api` and `svenja-game-v2` service names to resolve. Keep their services and credentials unchanged.
4. Rebuild the mainpage image so the new nginx snippets and HTML ship together. For a production Compose service actually named `mainpage`, the operator can use the following after setting `PRODUCTION_COMPOSE` to the correct file:

```bash
docker compose -f "$PRODUCTION_COMPOSE" build mainpage
docker compose -f "$PRODUCTION_COMPOSE" run --rm --no-deps mainpage nginx -t
# Only after review and successful syntax/network/asset checks:
docker compose -f "$PRODUCTION_COMPOSE" up -d --no-deps mainpage
```

5. Verify the real image has `/etc/ssl/certs/ca-certificates.crt` and that a real GitHub request succeeds with certificate verification. Purge any persistent old GitHub proxy cache via the existing operator-controlled cache procedure; fresh containers normally have fresh cache storage, but a volume may persist it.
6. Verify origin and public-edge responses for `/`, `/health`, `/llms.txt`, an asset, the allowed GitHub commit feeds, `/api/check-health`, an unknown path and an unauthorized `/github/user` path. Expect security headers on successes/errors/redirects and CSP outside Svenja. Check Cloudflare is not duplicating/overriding headers or serving stale HTML. Confirm homepage status, Activity commits, all menus/links, seasonal mode and existing Svenja routes still work.
7. Rollback: redeploy the saved previous mainpage image/configuration using the same production project while leaving untracked assets and unrelated API/game services untouched. HTML and CSP snippets must always roll forward/back together.

## Residual risks and blockers

- **No Docker engine:** no image build, Alpine-container `nginx -t`, image CVE scan, real container healthcheck/network validation or deployment was performed. The extracted Debian binary is a meaningful runtime test, not proof of the final image.
- Docker still references `nginx:1.27-alpine`, an old, mutable tag. A supported base-image upgrade and digest pin, with image vulnerability scanning and real container tests, remain a separate release task; no speculative untested image bump was made.
- HSTS/TLS/HTTP-to-HTTPS redirect policy belongs at the HTTPS-terminating Cloudflare edge. No HSTS includeSubDomains/preload was guessed from plain-HTTP nginx behind a tunnel. Verify edge policy separately before enabling long-lived HSTS.
- `docker-compose.yml` still publishes `8000:8000` on all interfaces. Firewall or loopback-only publication/private Docker networking should prevent public origin bypass of tunnel/edge controls; the actual production topology was not accessed or changed.
- No full repository-history or image-layer secret scan was performed. Ignore rules do not untrack existing files or rotate previously leaked credentials. No real secrets were discovered by this local heuristic check; do not infer that none ever existed.
- Svenja content, API internals/authentication, rate limiting, Cloudflare configuration and origin access control are not verified. Strict new CSP intentionally excludes Svenja. Basic global headers/extension guards should be smoke-tested against those routes before release.
- The GitHub allowlist must be deliberately updated if Activity gains another repository or endpoint. Existing cache expiry, public query arguments and GitHub rate limits remain; there is no claim of abuse-proof rate limiting.
- Browser validation covered Chromium, not Firefox/WebKit. Visual equality used deterministic local fixtures, not current live data. Some pre-existing malformed/incomplete HTML endings and outdated prose were deliberately left untouched to preserve content.

## Changed files

- `.dockerignore`, `.gitignore`: environment/key exclusions.
- `Dockerfile`: copy both nginx snippets.
- `nginx/default.conf`: shared headers, GitHub proxy hardening, secret-file guards.
- `nginx/csp.conf`, `nginx/security-headers.conf`: new CSP map and response-header snippet.
- `app/template/Activity.html`: safe commit rendering.
- `app/template/Projects.html`, `app/template/Services.html`: five opener-isolation attributes.
- `tests/activity-security.test.js`, `tests/test_security.py`, `tests/browser_security.py`: regression/integration/browser tests.
- `docs/security-audit.md`, `docs/security-verification.txt`: this report and exact final verification output.

Reference documentation consulted: nginx HTTP headers module (`https://nginx.org/en/docs/http/ngx_http_headers_module.html`) and proxy module (`https://nginx.org/en/docs/http/ngx_http_proxy_module.html`). No newer inheritance-only directive was used, preserving compatibility with the existing nginx line.
