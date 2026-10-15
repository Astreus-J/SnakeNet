"""Shared fixtures: a real UDP server on an ephemeral localhost port, pumped by the test thread."""
import socket
import pytest

from snakenet import protocol as P
from snakenet.config import ServerConfig
from snakenet.server import SnakeServer


def make_server(**overrides) -> SnakeServer:
    cfg = ServerConfig(host="127.0.0.1", port=0, seed=1, **overrides)
    server = SnakeServer(cfg)
    server.open()
    return server


@pytest.fixture
def server():
    s = make_server()
    yield s
    s.close()


class RawClient:
    """Minimal UDP peer for deterministic server tests (no threads)."""

    def __init__(self, server: SnakeServer) -> None:
        self.server = server
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(0.0)
        self.tok = None
        self.pid = None

    def send(self, data: bytes) -> None:
        self.sock.sendto(data, self.server.address)

    def msg(self, t: str, **f) -> None:
        self.send(P.encode(t, P.C2S, **f))

    def recv_all(self) -> list[dict]:
        out = []
        while True:
            try:
                data, _ = self.sock.recvfrom(4096)
            except (BlockingIOError, TimeoutError):
                return out
            out.append(P.decode(data, P.S2C))

    def join(self, name="p") -> dict:
        self.msg("JOIN", name=name)
        self.server.pump(0.05)
        welcome = next(m for m in self.recv_all() if m["t"] == "WELCOME")
        self.tok, self.pid = welcome["tok"], welcome["pid"]
        return welcome

    def close(self):
        self.sock.close()


@pytest.fixture
def client_factory(server):
    made = []

    def make():
        c = RawClient(server)
        made.append(c)
        return c

    yield make
    for c in made:
        c.close()
