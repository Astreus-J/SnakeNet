import socket
import time

from snakenet import protocol as P
from snakenet.client import ConnState, NetClient
from snakenet.config import ClientConfig, ServerConfig
from snakenet.server import SnakeServer


def wait_for(cond, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def running_server(**kw):
    server = SnakeServer(ServerConfig(host="127.0.0.1", port=0, seed=3, **kw))
    host, port = server.start_background()
    return server, host, port


def test_clients_join_see_each_other_and_leave_cleanly():
    server, host, port = running_server()
    a = NetClient(ClientConfig(host=host, port=port, name="ana"))
    b = NetClient(ClientConfig(host=host, port=port, name="bob"))
    try:
        a.start(), b.start()
        assert wait_for(lambda: a.snapshot().state is ConnState.CONNECTED and b.snapshot().state is ConnState.CONNECTED)
        assert a.snapshot().pid != b.snapshot().pid
        assert wait_for(lambda: a.snapshot().view and len(a.snapshot().view["snakes"]) == 2
                        and b.snapshot().view and len(b.snapshot().view["snakes"]) == 2)
        assert a.send_input("U") and not a.send_input("X")
        a.close(), b.close()
        assert a._sock.fileno() == -1  # socket released
        assert wait_for(lambda: not server.sessions)  # LEAVE processed
    finally:
        a.close(), b.close()
        server.shutdown()
    assert server.sock is None


def test_server_unavailable_reports_failure_without_crash():
    # Reserve a port, then free it so nothing is listening there.
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    c = NetClient(ClientConfig(host="127.0.0.1", port=port, join_attempts=3, join_interval=0.05))
    c.start()
    try:
        assert wait_for(lambda: c.snapshot().state is ConnState.FAILED)
        assert "unavailable" in c.snapshot().message
        assert c.send_input("U") is False
    finally:
        c.close()


def test_unresolvable_host_fails_immediately():
    c = NetClient(ClientConfig(host="no-such-host.invalid", port=5000))
    c.start()
    assert c.snapshot().state is ConnState.FAILED
    c.close()


def test_stale_and_duplicate_snapshots_are_ignored():
    c = NetClient(ClientConfig())
    c._state, c._tok = ConnState.CONNECTED, "0" * 16

    def state(seq, tick):
        return P.encode("STATE", P.S2C, seq=seq, tick=tick, snakes=[], food=[])

    c._handle(state(5, 50), 0.0)
    c._handle(state(3, 30), 0.0)   # older: stale
    c._handle(state(5, 50), 0.0)   # duplicate
    c._handle(state(6, 60), 0.0)
    snap = c.snapshot()
    assert snap.view["seq"] == 6 and snap.stale_dropped == 2


def test_malformed_server_datagram_is_ignored():
    c = NetClient(ClientConfig())
    c._state, c._tok = ConnState.CONNECTED, "0" * 16
    c._handle(b"\xff garbage", 0.0)
    c._handle(b'{"v":1,"t":"STATE"}', 0.0)
    assert c.snapshot().view is None and c.snapshot().state is ConnState.CONNECTED


def test_connection_lost_then_recovers_after_server_comes_back():
    server, host, port = running_server()
    c = NetClient(ClientConfig(host=host, port=port, name="x", lost_after=0.4, join_attempts=40, join_interval=0.1))
    try:
        c.start()
        assert wait_for(lambda: c.snapshot().state is ConnState.CONNECTED)
        server.shutdown()  # clean shutdown sends SERVER_SHUTDOWN
        assert wait_for(lambda: c.snapshot().state is ConnState.FAILED)
        assert "SERVER_SHUTDOWN" in c.snapshot().message
        # restart on the same port, then manual retry
        server2 = SnakeServer(ServerConfig(host=host, port=port, seed=4))
        server2.start_background()
        try:
            c.retry()
            assert wait_for(lambda: c.snapshot().state is ConnState.CONNECTED)
            assert wait_for(lambda: c.snapshot().view is not None)  # seq counter restarted, not dropped as stale
        finally:
            server2.shutdown()
    finally:
        c.close()


def test_session_expiry_triggers_automatic_rejoin():
    server, host, port = running_server(session_timeout=0.5)
    c = NetClient(ClientConfig(host=host, port=port, name="x"))
    try:
        c.start()
        assert wait_for(lambda: c.snapshot().state is ConnState.CONNECTED)
        first = c.snapshot().pid
        # Make the server forget this session as if it had timed out.
        for s in list(server.sessions.values()):
            server._drop_session(s)
        assert wait_for(lambda: c.snapshot().pid not in (None, first) and c.snapshot().state is ConnState.CONNECTED, 5.0)
    finally:
        c.close()
        server.shutdown()
