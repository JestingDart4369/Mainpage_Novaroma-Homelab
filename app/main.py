from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx

app = FastAPI(
    title="NovaRoma Homelab - Main Page",
    description="Personal portfolio and project showcase",
    version="1.0.0"
)

# Enable CORS for all origins (adjust in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    """Serve the homepage of the api"""
    template_path = Path(__file__).parent / "template" / "page.html"
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "mainpage"}

@app.get("/api/check-health")
async def check_api_health():
    """Proxy endpoint to check external API health (avoids CORS issues)"""
    api_url = "https://api.novaroma-homelab.uk/health"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(api_url)
            return {
                "status": "online" if response.status_code == 200 else "offline",
                "status_code": response.status_code,
                "api_response": response.json() if response.status_code == 200 else None
            }
    except Exception as e:
        return {
            "status": "offline",
            "error": str(e)
        }