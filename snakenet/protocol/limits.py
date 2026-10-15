"""Wire-format constants: protocol version and size limits."""
from __future__ import annotations

PROTOCOL_VERSION = 1

# Largest datagram the server accepts from a client. Real client messages are < 150 bytes.
MAX_C2S_BYTES = 1024
# Largest datagram the server emits: Ethernet MTU 1500 - 20 (IPv4) - 8 (UDP), so a STATE
# snapshot is never IP-fragmented (a lost fragment would lose the whole snapshot).
MAX_S2C_BYTES = 1472

DIRECTIONS = ("U", "D", "L", "R")
NAME_MAX = 12
MAX_SNAKES_IN_STATE = 16
MAX_FOOD_IN_STATE = 64
MAX_BODY_CHARS = 128
