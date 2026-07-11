#!/bin/bash
# Wrapper that runs the Discord bot and automatically restarts it if it
# crashes. A clean exit (code 0, e.g. a deliberate shutdown) still restarts
# by default — remove the loop or add an exit-code check below if you want
# clean exits to stop the loop instead.
cd "$(dirname "$0")"

RESTART_DELAY=5

while true; do
  echo "[run.sh] $(date -u '+%Y-%m-%dT%H:%M:%SZ') Starting bot..."
  python3 main.py
  EXIT_CODE=$?
  echo "[run.sh] $(date -u '+%Y-%m-%dT%H:%M:%SZ') Bot exited with code $EXIT_CODE. Restarting in ${RESTART_DELAY}s..."
  sleep "$RESTART_DELAY"
done
