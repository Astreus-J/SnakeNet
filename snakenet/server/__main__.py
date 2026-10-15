"""CLI entry point:  python -m snakenet.server --host 0.0.0.0 --port 5000"""
from __future__ import annotations

import argparse
import logging
import signal
import sys

from ..config import ServerConfig
from .app import ServerStartError, SnakeServer

log = logging.getLogger("snakenet.server")


def main(argv: list[str] | None = None) -> int:
    d = ServerConfig()
    ap = argparse.ArgumentParser(description="SnakeNet authoritative UDP game server")
    ap.add_argument("--host", default=ServerConfig.default_host(), help="bind address (0.0.0.0 for LAN) [env SNAKENET_HOST]")
    ap.add_argument("--port", type=int, default=ServerConfig.default_port(), help="UDP port [env SNAKENET_PORT]")
    ap.add_argument("--tick-rate", type=float, default=d.tick_rate)
    ap.add_argument("--snapshot-rate", type=float, default=d.snapshot_rate)
    ap.add_argument("--session-timeout", type=float, default=d.session_timeout)
    ap.add_argument("--max-players", type=int, default=d.max_players)
    ap.add_argument("--seed", type=int, default=None, help="RNG seed (reproducible food/spawns)")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    if not 1 <= a.port <= 65535 or a.snapshot_rate <= 0 or a.tick_rate <= 0 or a.snapshot_rate > a.tick_rate:
        ap.error("invalid port or rates (need 0 < snapshot-rate <= tick-rate)")
    if a.session_timeout < 0.5:
        ap.error("--session-timeout must be >= 0.5 (protocol WELCOME.timeout lower bound)")
    cfg = ServerConfig(host=a.host, port=a.port, tick_rate=a.tick_rate, snapshot_rate=a.snapshot_rate,
                       session_timeout=a.session_timeout, max_players=a.max_players, seed=a.seed)
    server = SnakeServer(cfg)
    # Graceful stop on Ctrl-C and SIGTERM (systemd/docker): notify clients, release the socket.
    # SIGINT is re-armed explicitly because background jobs inherit "ignore SIGINT".
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, signal.default_int_handler)
    try:
        server.open()
    except ServerStartError as exc:
        log.error("%s", exc)
        return 2
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("interrupted, shutting down")
        server.close()
    return 0



if __name__ == "__main__":
    sys.exit(main())
