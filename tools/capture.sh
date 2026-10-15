#!/usr/bin/env bash
# Capture SnakeNet UDP traffic to evidence/snakenet.pcapng with dumpcap (ships with Wireshark).
# Usage: tools/capture.sh [interface] [port]     e.g.  tools/capture.sh lo 5000
# Needs capture permission (run as root, or add your user to the 'wireshark' group).
set -euo pipefail
IFACE="${1:-lo}"
PORT="${2:-5000}"
OUT="$(dirname "$0")/../evidence/snakenet.pcapng"
mkdir -p "$(dirname "$OUT")"
echo "Capturing UDP port $PORT on '$IFACE' -> $OUT  (Ctrl-C to stop)"
exec dumpcap -i "$IFACE" -f "udp port $PORT" -w "$OUT"
