"""Authoritative SnakeNet UDP server.

Single-threaded on purpose: one loop does receive -> validate -> simulate -> broadcast, so
game state is never touched concurrently and a slow client cannot block the simulation
(UDP ``sendto`` never waits for the receiver).

Entry point: server/__main__.py
"""
from __future__ import annotations

import logging
import random
import secrets
import socket
import threading
import time
from dataclasses import dataclass
from typing import Callable

from .. import protocol as P
from ..config import ServerConfig
from ..game import World
from .sessions import Session
from .throttle import ErrorBudget, ThrottledLog

log = logging.getLogger("snakenet.server")

MAX_DATAGRAMS_PER_PUMP = 256  # bound work per loop iteration so ticks are never starved
MAX_CATCHUP_TICKS = 5         # if the loop falls behind, skip instead of spiralling


class ServerStartError(RuntimeError):
    """The UDP socket could not be created or bound."""


@dataclass
class Stats:
    rx: int = 0
    tx: int = 0
    rejected: int = 0
    duplicates: int = 0
    rate_limited: int = 0
    expired: int = 0
    send_errors: int = 0


class SnakeServer:
    def __init__(
        self,
        config: ServerConfig,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.cfg = config
        self.clock = clock
        self.world = World(
            config.width, config.height, config.food_target, config.respawn_ticks,
            max_length=config.max_length, rng=random.Random(config.seed),
        )
        self.sessions: dict[str, Session] = {}      # token -> session
        self.by_addr: dict[tuple[str, int], Session] = {}
        self.stats = Stats()
        self.sock: socket.socket | None = None
        self._next_pid = 1
        self._snapshot_seq = 0
        self._tick_interval = 1.0 / config.tick_rate
        self._snapshot_every = max(1, round(config.tick_rate / config.snapshot_rate))
        self._next_tick = 0.0
        self._error_budget = ErrorBudget()
        self._throttled_log = ThrottledLog(log)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------ lifecycle
    def open(self) -> tuple[str, int]:
        """Create and bind the UDP socket. Returns the bound (host, port)."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # NOTE: no SO_REUSEADDR. On Linux it would let a second server bind the same
            # UDP port silently, hiding the "port already in use" error we want to report.
            sock.bind((self.cfg.host, self.cfg.port))
        except OSError as exc:
            raise ServerStartError(
                f"cannot bind UDP {self.cfg.host}:{self.cfg.port}: {exc.strerror or exc}"
            ) from exc
        self.sock = sock
        self._next_tick = self.clock() + self._tick_interval
        return sock.getsockname()

    @property
    def address(self) -> tuple[str, int]:
        assert self.sock is not None, "server not open"
        return self.sock.getsockname()

    def serve_forever(self) -> None:
        if self.sock is None:
            self.open()
        log.info("listening on UDP %s:%d (tick %.0f Hz, timeout %.1fs)", *self.address,
                 self.cfg.tick_rate, self.cfg.session_timeout)
        try:
            while not self._stop.is_set():
                self.pump(max_wait=0.05)
        finally:
            self.close()

    def start_background(self) -> tuple[str, int]:
        addr = self.open() if self.sock is None else self.address
        self._thread = threading.Thread(target=self.serve_forever, name="snakenet-server", daemon=True)
        self._thread.start()
        return addr

    def shutdown(self) -> None:
        """Stop the loop (if running in a thread) and release the socket."""
        self._stop.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=2.0)
        self.close()

    def close(self) -> None:
        if self.sock is None:
            return
        for s in list(self.sessions.values()):
            self._send_error(s.addr, P.SERVER_SHUTDOWN, "server is shutting down", force=True)
        self.sock.close()
        self.sock = None
        self.sessions.clear()
        self.by_addr.clear()
        log.info("server closed")

    # ------------------------------------------------------------------ main loop
    def pump(self, max_wait: float | None = None) -> None:
        """One loop iteration: receive datagrams (waiting at most until the next tick), then run due ticks."""
        if self.sock is None:
            return
        wait = max(0.0, self._next_tick - self.clock())
        if max_wait is not None:
            wait = min(wait, max_wait)
        self._receive_batch(wait)
        self._run_due_ticks()

    def _receive_batch(self, wait: float) -> None:
        sock = self.sock
        assert sock is not None
        sock.settimeout(wait)
        for _ in range(MAX_DATAGRAMS_PER_PUMP):
            try:
                # +1 byte so an oversized datagram is detected rather than silently truncated
                data, addr = sock.recvfrom(P.MAX_C2S_BYTES + 1)
            except (BlockingIOError, TimeoutError):
                return
            except ConnectionResetError:
                continue  # Windows reports ICMP "port unreachable" from a previous sendto
            except OSError as exc:
                self._warn("recv", "recv failed: %s", exc)
                return
            sock.settimeout(0.0)  # drain whatever is already queued without blocking
            try:
                self._handle_datagram(data, addr, self.clock())
            except Exception:  # noqa: BLE001 - a bad packet must never kill the server
                self._warn("handler", "unexpected error handling datagram from %s", addr, exc_info=True)

    def _run_due_ticks(self) -> None:
        now = self.clock()
        ran = 0
        while now >= self._next_tick and ran < MAX_CATCHUP_TICKS:
            try:
                self._tick(now)
            except Exception:  # noqa: BLE001
                self._warn("tick", "unexpected error in tick", exc_info=True)
            self._next_tick += self._tick_interval
            ran += 1
        if now >= self._next_tick:  # still behind: drop the backlog
            self._next_tick = now + self._tick_interval

    def _tick(self, now: float) -> None:
        self._expire_sessions(now)
        for pid, reason in self.world.step():
            log.info("player %d died (%s)", pid, reason)
        if self.world.tick % self._snapshot_every == 0:
            self._broadcast_state()

    # ------------------------------------------------------------------ datagram handling
    def _handle_datagram(self, data: bytes, addr: tuple[str, int], now: float) -> None:
        self.stats.rx += 1
        try:
            msg = P.decode(data, P.C2S)
        except P.ProtocolError as exc:
            self.stats.rejected += 1
            self._warn(("bad", exc.code), "rejected datagram from %s:%d: %s", *addr, exc)
            self._send_error(addr, exc.code, exc.detail)
            return

        kind = msg["t"]
        if kind == "JOIN":
            self._on_join(msg, addr, now)
            return
        session = self.sessions.get(msg["tok"])
        if session is None or session.addr != addr:  # unknown token OR token used from another address
            if kind != "LEAVE":  # LEAVE is idempotent: leaving twice is not an error
                self._send_error(addr, P.BAD_SESSION, "unknown or expired session", ref=kind)
            return
        session.last_seen = now

        if kind == "INPUT":
            self._on_input(session, msg, now)
        elif kind == "PING":
            self._send(addr, P.encode("PONG", P.S2C, seq=msg["seq"], ts=msg["ts"], tick=self.world.tick))
        elif kind == "LEAVE":
            log.info("player %d (%s) left", session.pid, session.name)
            self._drop_session(session)

    def _on_join(self, msg: dict, addr: tuple[str, int], now: float) -> None:
        session = self.by_addr.get(addr)
        if session is None:
            if len(self.sessions) >= self.cfg.max_players:
                self._send_error(addr, P.SERVER_FULL, f"match is full ({self.cfg.max_players} players)", ref="JOIN")
                return
            session = Session(
                pid=self._next_pid, token=secrets.token_hex(8), addr=addr, name=msg["name"],
                last_seen=now, bucket=float(self.cfg.input_burst), bucket_t=now,
            )
            self._next_pid += 1
            self.sessions[session.token] = session
            self.by_addr[addr] = session
            self.world.add_player(session.pid, session.name)
            log.info("player %d (%s) joined from %s:%d", session.pid, session.name, *addr)
        else:
            # Retried JOIN (the WELCOME was probably lost): idempotent, same pid/token.
            session.last_seen = now
        self._send(addr, P.encode(
            "WELCOME", P.S2C, pid=session.pid, tok=session.token, w=self.world.width,
            h=self.world.height, tick_rate=self.cfg.tick_rate, timeout=self.cfg.session_timeout,
        ))

    def _on_input(self, session: Session, msg: dict, now: float) -> None:
        if not session.allow_input(now, self.cfg.input_rate, self.cfg.input_burst):
            self.stats.rate_limited += 1
            self._warn(("rate", session.pid), "player %d is sending inputs too fast", session.pid)
            self._send_error(session.addr, P.RATE_LIMITED, "too many INPUT messages", ref="INPUT")
            return
        # Duplicate or reordered datagram (or a deliberate redundant copy): ignore, idempotent.
        if not session.accept_input_seq(msg["seq"]):
            self.stats.duplicates += 1
            return
        self.world.set_direction(session.pid, msg["dir"])  # False (reverse/dead) is simply ignored

    # ------------------------------------------------------------------ sessions & sending
    def _drop_session(self, session: Session) -> None:
        self.sessions.pop(session.token, None)
        self.by_addr.pop(session.addr, None)
        self.world.remove_player(session.pid)

    def _expire_sessions(self, now: float) -> None:
        for s in [s for s in self.sessions.values() if now - s.last_seen > self.cfg.session_timeout]:
            log.info("player %d (%s) timed out", s.pid, s.name)
            self.stats.expired += 1
            self._drop_session(s)
            self._send_error(s.addr, P.SESSION_EXPIRED, "session timed out", force=True)

    def _broadcast_state(self) -> None:
        if not self.sessions:
            return
        self._snapshot_seq += 1
        snakes, food = self.world.snapshot()
        try:
            data = P.encode("STATE", P.S2C, seq=self._snapshot_seq, tick=self.world.tick, snakes=snakes, food=food)
        except P.ProtocolError as exc:
            self._warn("state-size", "cannot send snapshot: %s", exc)
            return
        for s in self.sessions.values():
            self._send(s.addr, data)

    def _send(self, addr: tuple[str, int], data: bytes) -> None:
        if self.sock is None:
            return
        try:
            self.sock.sendto(data, addr)
            self.stats.tx += 1
        except OSError as exc:  # e.g. network unreachable, buffer full: UDP is best-effort
            self.stats.send_errors += 1
            self._warn("send", "sendto %s failed: %s", addr, exc)

    def _send_error(self, addr: tuple[str, int], code: str, msg: str, ref: str | None = None, force: bool = False) -> None:
        now = self.clock()
        if not force and not self._error_budget.allow(addr, now):
            return
        fields = {"code": code, "msg": msg[:120]}
        if ref:
            fields["ref"] = ref
        self._send(addr, P.encode("ERROR", P.S2C, **fields))

    def _warn(self, key: object, fmt: str, *args: object, exc_info: bool = False) -> None:
        self._throttled_log.warn(self.clock(), key, fmt, *args, exc_info=exc_info)
