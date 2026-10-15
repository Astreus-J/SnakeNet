"""Client networking: owns the UDP socket and a receive thread. No pygame here.

The UI thread only calls ``send_input`` / ``snapshot`` / ``close``; the network thread does all
receiving, JOIN retries, keep-alives and loss detection. Shared state is guarded by one lock.
"""
from __future__ import annotations

import logging
import socket
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .. import protocol as P
from ..config import ClientConfig

log = logging.getLogger("snakenet.client")


class ConnState(str, Enum):
    JOINING = "joining"      # waiting for WELCOME (bounded retries)
    CONNECTED = "connected"
    LOST = "lost"            # no datagrams from server; re-joining automatically
    FAILED = "failed"        # gave up: timeout, rejected, or server gone
    CLOSED = "closed"


@dataclass(frozen=True)
class ClientSnapshot:
    state: ConnState
    message: str
    pid: int | None
    width: int
    height: int
    view: dict[str, Any] | None   # latest accepted STATE message (validated)
    rtt_ms: float | None
    rx: int
    tx: int
    stale_dropped: int


class NetClient:
    def __init__(self, config: ClientConfig) -> None:
        self.cfg = config
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._sock: socket.socket | None = None
        self._server: tuple[str, int] | None = None
        # ---- shared (guarded by _lock) ----
        self._state = ConnState.JOINING
        self._message = "connecting..."
        self._pid: int | None = None
        self._tok: str | None = None
        self._w = self._h = 0
        self._view: dict[str, Any] | None = None
        self._last_state_seq = -1
        self._rtt: float | None = None
        self._input_seq = 0
        self._ping_seq = 0
        self._rx = self._tx = self._stale = 0
        self._ping_interval = 1.0
        # ---- network-thread only ----
        self._attempts_left = 0
        self._next_join = 0.0
        self._last_rx = 0.0
        self._last_ping = 0.0

    # ------------------------------------------------------------------ public API (UI thread)
    def start(self) -> None:
        try:
            infos = socket.getaddrinfo(self.cfg.host, self.cfg.port, socket.AF_INET, socket.SOCK_DGRAM)
            self._server = infos[0][4]
        except (socket.gaierror, OSError) as exc:
            self._set(ConnState.FAILED, f"cannot resolve '{self.cfg.host}': {exc}")
            return
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.settimeout(0.05)  # short timeout: the thread wakes often to run timers and see stop
        self._begin_join()
        self._thread = threading.Thread(target=self._run, name="snakenet-net", daemon=True)
        self._thread.start()

    def retry(self) -> None:
        """Manual reconnect after FAILED."""
        if self._sock is not None and not self._stop.is_set():
            with self._lock:
                self._tok = None
                self._view = None
            self._begin_join()

    def send_input(self, direction: str) -> bool:
        """Send a direction (twice, same seq, for loss tolerance). False if not connected/invalid."""
        if direction not in P.DIRECTIONS:
            return False
        with self._lock:
            if self._state is not ConnState.CONNECTED or self._tok is None:
                return False
            self._input_seq += 1
            data = P.encode("INPUT", P.C2S, tok=self._tok, seq=self._input_seq, dir=direction)
        for _ in range(max(1, self.cfg.input_redundancy)):
            self._send(data)
        return True

    def snapshot(self) -> ClientSnapshot:
        with self._lock:
            return ClientSnapshot(self._state, self._message, self._pid, self._w, self._h, self._view,
                                  self._rtt, self._rx, self._tx, self._stale)

    def close(self) -> None:
        """Leave politely (LEAVE x2, idempotent), stop the thread, release the socket."""
        if self._stop.is_set():
            return
        with self._lock:
            tok, connected = self._tok, self._state is ConnState.CONNECTED
        if connected and tok:
            data = P.encode("LEAVE", P.C2S, tok=tok)
            self._send(data)
            self._send(data)
        self._stop.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.0)
        if self._sock is not None:
            self._sock.close()
        self._set(ConnState.CLOSED, "closed")

    # ------------------------------------------------------------------ internals
    def _set(self, state: ConnState, message: str) -> None:
        with self._lock:
            self._state, self._message = state, message

    def _begin_join(self) -> None:
        self._attempts_left = self.cfg.join_attempts
        self._next_join = 0.0
        self._last_rx = time.monotonic()
        self._set(ConnState.JOINING, "connecting...")

    def _send(self, data: bytes) -> None:
        sock = self._sock
        if sock is None or self._server is None:
            return
        try:
            sock.sendto(data, self._server)
            with self._lock:
                self._tx += 1
        except OSError as exc:  # network unreachable etc.: best effort, timers will report loss
            log.debug("sendto failed: %s", exc)

    def _run(self) -> None:
        sock = self._sock
        assert sock is not None
        while not self._stop.is_set():
            try:
                self._timers(time.monotonic())
                try:
                    data, addr = sock.recvfrom(4096)
                except (TimeoutError, BlockingIOError):
                    continue
                except ConnectionResetError:
                    continue  # ICMP port unreachable surfaced by the OS; timers detect it
                except OSError:
                    if self._stop.is_set():
                        return
                    time.sleep(0.05)
                    continue
                if addr != self._server:
                    continue  # ignore datagrams not from our server
                self._handle(data, time.monotonic())
            except Exception:  # noqa: BLE001 - the net thread must survive any bad datagram
                log.exception("unexpected error in network thread")

    def _timers(self, now: float) -> None:
        with self._lock:
            state, tok = self._state, self._tok
        if state in (ConnState.JOINING, ConnState.LOST):
            if now >= self._next_join:
                if self._attempts_left > 0:
                    self._attempts_left -= 1
                    self._next_join = now + self.cfg.join_interval
                    self._send(P.encode("JOIN", P.C2S, name=self.cfg.name))
                else:
                    self._set(ConnState.FAILED, f"server unavailable (no WELCOME after {self.cfg.join_attempts} attempts)")
        elif state is ConnState.CONNECTED and tok:
            if now - self._last_rx > self.cfg.lost_after:
                self._attempts_left = self.cfg.join_attempts
                self._next_join = 0.0
                self._set(ConnState.LOST, "connection lost: no updates from server, reconnecting...")
            elif now - self._last_ping >= self._ping_interval:
                self._last_ping = now
                with self._lock:
                    self._ping_seq += 1
                    seq = self._ping_seq
                self._send(P.encode("PING", P.C2S, tok=tok, seq=seq, ts=now))

    def _handle(self, data: bytes, now: float) -> None:
        try:
            msg = P.decode(data, P.S2C)
        except P.ProtocolError as exc:
            log.debug("ignored bad datagram from server: %s", exc)
            return
        self._last_rx = now
        kind = msg["t"]
        with self._lock:
            self._rx += 1
            if kind == "WELCOME":
                if self._state is ConnState.CONNECTED and msg["tok"] == self._tok:
                    return  # duplicate WELCOME from a retried JOIN: do nothing
                self._pid, self._tok = msg["pid"], msg["tok"]
                self._w, self._h = msg["w"], msg["h"]
                self._ping_interval = max(0.2, msg["timeout"] / 3)
                self._last_state_seq = -1  # a new session / restarted server restarts the counter
                self._view = None
                self._state, self._message = ConnState.CONNECTED, "connected"
            elif kind == "STATE":
                if self._state is not ConnState.CONNECTED:
                    return
                if msg["seq"] <= self._last_state_seq:
                    self._stale += 1  # stale or duplicated snapshot: discard
                    return
                self._last_state_seq = msg["seq"]
                self._view = msg
            elif kind == "PONG":
                self._rtt = max(0.0, (now - msg["ts"]) * 1000.0)
            elif kind == "ERROR":
                self._on_error(msg)

    def _on_error(self, msg: dict[str, Any]) -> None:  # called with lock held
        code = msg["code"]
        text = f"{code}: {msg['msg']}"
        if code in (P.BAD_SESSION, P.SESSION_EXPIRED):
            if self._state is ConnState.CONNECTED:
                self._tok = None
                self._attempts_left = self.cfg.join_attempts
                self._next_join = 0.0
                self._state, self._message = ConnState.LOST, f"{text}; rejoining..."
        elif code in (P.SERVER_FULL, P.BAD_VERSION, P.SERVER_SHUTDOWN):
            self._state, self._message = ConnState.FAILED, text
        else:
            self._message = text  # informational (RATE_LIMITED, BAD_FIELD, ...)
            log.warning("server error: %s", text)
