#!/bin/sh
set -e

MODE="${RUN_MODE:-webapp}"

echo "========================================="
echo "Starting UNO Application in RUN_MODE=${MODE}"
echo "========================================="

if [ "$MODE" = "webapp" ]; then
    PORT_TO_USE="${PORT:-8000}"
    echo "[STARTUP] Launching FastAPI WebApp server via uvicorn on port ${PORT_TO_USE}..."
    exec uvicorn app:app --host 0.0.0.0 --port "${PORT_TO_USE}"
elif [ "$MODE" = "bot" ]; then
    echo "[STARTUP] Launching Telegram Bot poller via python bot.py..."
    exec python bot.py
else
    echo "[ERROR] Unknown RUN_MODE='$MODE'. Valid options are 'webapp' or 'bot'."
    exit 1
fi
