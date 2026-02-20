#!/bin/bash
# Start the FastAPI development server

echo "Starting NovaRoma Homelab Mainpage..."
echo

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Creating one..."
    python3 -m venv .venv
    echo
    echo "Installing dependencies..."
    .venv/bin/pip install -r requirements.txt
    echo
fi

# Activate virtual environment and run
source .venv/bin/activate
echo "Running server at http://localhost:8000"
echo "Press Ctrl+C to stop the server"
echo
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000