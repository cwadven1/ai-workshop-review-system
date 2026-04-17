#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

source venv/bin/activate

echo "[Celery] Starting worker..."
celery -A config worker --loglevel=info &
WORKER_PID=$!

echo "[Celery Beat] Starting beat scheduler..."
celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler &
BEAT_PID=$!

echo "Worker PID: $WORKER_PID"
echo "Beat PID:   $BEAT_PID"
echo "Press Ctrl+C to stop both."

trap "echo 'Stopping...'; kill $WORKER_PID $BEAT_PID; exit 0" SIGINT SIGTERM

wait
