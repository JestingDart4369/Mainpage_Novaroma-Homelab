@echo off
REM Start the FastAPI development server

echo Starting NovaRoma Homelab Mainpage...
echo.

REM Check if virtual environment exists
if not exist ".venv\" (
    echo Virtual environment not found. Creating one...
    python -m venv .venv
    echo.
    echo Installing dependencies...
    .venv\Scripts\pip install -r requirements.txt
    echo.
)

REM Activate virtual environment and run
call .venv\Scripts\activate.bat
echo Running server at http://localhost:8000
echo Press Ctrl+C to stop the server
echo.
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000