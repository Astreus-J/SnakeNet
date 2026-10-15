"""Headless autopilot client (no pygame): for demos, load tests and Wireshark captures.

Run:  python -m snakenet.client.bot --host 127.0.0.1 --port 5000 --name bot1 --duration 30
"""
from __future__ import annotations

import argparse
import sys
import time

from .network import ConnState, NetClient
from ..config import ClientConfig, ServerConfig
from ..game import DELTAS, OPPOSITE, decode_body


def choose_direction(view: dict, pid: int, width: int, height: int) -> str | None:
    """Greedy: step towards the nearest food among moves that don't hit a wall or a body."""
    me = next((s for s in view["snakes"] if s["id"] == pid and s["a"]), None)
    if me is None:
        return None
    blocked = set()
    for s in view["snakes"]:
        if s["a"]:
            blocked.update(decode_body(s["x"], s["y"], s["d"])[:-1])  # tail cell will be vacated
    hx, hy = me["x"], me["y"]
    current = None  # direction of travel, derived from the neck cell below
    body = decode_body(hx, hy, me["d"])
    if len(body) > 1:
        nx, ny = body[1]
        current = next((d for d, (dx, dy) in DELTAS.items() if (hx - dx, hy - dy) == (nx, ny)), None)
    food = view["food"]
    best, best_score = None, 1e9
    for d, (dx, dy) in DELTAS.items():
        if current and d == OPPOSITE[current]:
            continue
        x, y = hx + dx, hy + dy
        if not (0 <= x < width and 0 <= y < height) or (x, y) in blocked:
            continue
        dist = min((abs(fx - x) + abs(fy - y) for fx, fy in food), default=0)
        if dist < best_score:
            best, best_score = d, dist
    return best


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SnakeNet bot client")
    ap.add_argument("--host", default=ServerConfig.default_host())
    ap.add_argument("--port", type=int, default=ServerConfig.default_port())
    ap.add_argument("--name", default="bot")
    ap.add_argument("--duration", type=float, default=30.0, help="seconds to play")
    a = ap.parse_args(argv)
    net = NetClient(ClientConfig(host=a.host, port=a.port, name=a.name[:12] or "bot"))
    net.start()
    end = time.monotonic() + a.duration
    last_tick = -1
    try:
        while time.monotonic() < end:
            snap = net.snapshot()
            if snap.state is ConnState.FAILED:
                print(f"bot {a.name}: {snap.message}", file=sys.stderr)
                return 1
            if snap.view and snap.pid and snap.view["tick"] != last_tick:
                last_tick = snap.view["tick"]
                d = choose_direction(snap.view, snap.pid, snap.width, snap.height)
                if d:
                    net.send_input(d)
            time.sleep(0.02)
    except KeyboardInterrupt:
        pass
    finally:
        net.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
