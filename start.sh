#!/usr/bin/env bash
# Script to launch both UNO FastAPI Backend and Vite Frontend concurrently

echo "=================================================="
echo " Starting UNO WebApp: Backend (8000) & Frontend (8080)"
echo "=================================================="

# Function to kill child processes on exit
cleanup() {
    echo ""
    echo "Stopping servers..."
    kill $(jobs -p) 2>/dev/null
    exit 0
}

trap cleanup EXIT INT TERM

# 1. Start Python FastAPI Backend Server
echo "[1/2] Launching FastAPI Backend on http://localhost:8000 ..."
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload --reload-exclude front-end &
BACKEND_PID=$!

# Wait briefly for FastAPI to initialize
sleep 2

# 2. Start Vite Frontend Development Server
echo "[2/2] Launching Vite Frontend on http://localhost:8080 ..."
cd front-end && npm run dev

wait
