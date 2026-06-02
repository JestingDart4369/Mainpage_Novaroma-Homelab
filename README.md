# NovaRoma Homelab - Mainpage

Static personal portfolio and project showcase for JestingDart4369.

## Tech Stack

- **Hosting**: nginx static web server
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Deployment**: Docker + Cloudflare Tunnel

## Structure

```text
app/template/
├── index.html          # Static portfolio page
├── page.html           # Same page source kept for compatibility
├── favicon.ico
├── favicon-32.png
└── images/
    ├── Nova-roma_logo.png
    ├── favicon.ico
    └── favicon-32.png
nginx/default.conf      # nginx routes, static hosting, /health, API health proxy
Dockerfile              # nginx-based container
```

## Routes

- `/` serves the static site
- `/favicon.ico` serves the favicon directly from nginx
- `/favicon-32.png` serves the PNG favicon
- `/health` returns a static JSON health response
- `/api/check-health` proxies to the API container's `/health` endpoint for the homepage status indicator

## Local Docker Run

```bash
docker build -t novaroma-mainpage .
docker run --rm -p 8000:8000 novaroma-mainpage
```

Then open <http://localhost:8000>.

## Production

Production URL: <https://novaroma-homelab.uk>

The container is intended to run on the shared Docker Compose network with Cloudflare Tunnel pointing to `novaroma-mainpage:8000`.
