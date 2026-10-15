#!/usr/bin/env bash
# Local demo: 1 server + 2 bots (headless) so you can watch/capture traffic. Ctrl-C stops everything.
# Usage: tools/demo_local.sh [port] [seconds]
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${1:-5000}"; SECS="${2:-60}"
PY="${PYTHON:-.venv/bin/python}"
"$PY" -m snakenet.server --host 127.0.0.1 --port "$PORT" & SERVER=$!
trap 'kill $SERVER $B1 $B2 2>/dev/null || true' EXIT INT TERM
sleep 1
"$PY" -m snakenet.client.bot --port "$PORT" --name bot1 --duration "$SECS" & B1=$!
"$PY" -m snakenet.client.bot --port "$PORT" --name bot2 --duration "$SECS" & B2=$!
echo "Server on UDP 127.0.0.1:$PORT with 2 bots for ${SECS}s. Start a human client: $PY -m snakenet.client --port $PORT"
wait $B1 $B2
