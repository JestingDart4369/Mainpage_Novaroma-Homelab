# NovaRoma Homelab - Mainpage

Personal portfolio and project showcase for JestingDart4369.

## Features

- Modern glassmorphic design with gradient backgrounds
- Automatic dark/light theme switching
- Animated particle background
- Live GitHub repository stats integration
- Latest commits feed
- API health monitoring
- Responsive design

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Deployment**: Docker + Cloudflare Tunnel

## Setup

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Run Development Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Access the Application

Open your browser and navigate to:
- **Main page**: http://localhost:8000
- **API docs**: http://localhost:8000/docs
- **Health check**: http://localhost:8000/health

## Project Structure

```
01_Mainpage/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   └── template/
│       └── page.html        # Portfolio HTML page
├── .venv/                   # Virtual environment (ignored)
├── .gitignore
├── requirements.txt
├── LICENSE
└── README.md
```

## Deployment

The application is designed to run in Docker and be exposed via Cloudflare Tunnel:

- Production URL: https://novaroma-homelab.uk
- API URL: https://api.novaroma-homelab.uk

## License

See [LICENSE](LICENSE) file for details.

## Author

JestingDart4369
- GitHub: [@JestingDart4369](https://github.com/JestingDart4369)
- Domain: novaroma-homelab.uk