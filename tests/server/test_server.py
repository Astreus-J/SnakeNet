import socket
import time

import pytest

from snakenet import protocol as P
from snakenet.server import ServerStartError, SnakeServer
from snakenet.config import ServerConfig
from conftest import make_server


def pump(server, n=3):
    for _ in range(n):
        server.pump(0.02)


def test_join_assigns_unique_ids_and_tokens(server, client_factory):
    a, b = client_factory(), client_factory()
    wa, wb = a.join("ana"), b.join("bob")
    assert wa["pid"] != wb["pid"] and wa["tok"] != wb["tok"]
    assert (wa["w"], wa["h"]) == (60, 40)
    assert len(server.sessions) == 2 and len(server.world.snakes) == 2


def test_duplicate_join_is_idempotent(server, client_factory):
    a = client_factory()
    first = a.join("ana")
    a.msg("JOIN", name="ana")
    pump(server)
    again = [m for m in a.recv_all() if m["t"] == "WELCOME"][0]
    assert (again["pid"], again["tok"]) == (first["pid"], first["tok"])
    assert len(server.sessions) == 1 and len(server.world.snakes) == 1


def test_two_clients_receive_identical_state(server, client_factory):
    a, b = client_factory(), client_factory()
    a.join(), b.join()
    time.sleep(0.2)
    pump(server, 5)
    sa = {m["seq"]: m for m in a.recv_all() if m["t"] == "STATE"}
    sb = {m["seq"]: m for m in b.recv_all() if m["t"] == "STATE"}
    common = sa.keys() & sb.keys()
    assert common
    for seq in common:
        assert sa[seq] == sb[seq]
    assert sorted(s["id"] for s in sa[max(common)]["snakes"]) == sorted([a.pid, b.pid])


def test_input_only_affects_sender(server, client_factory):
    a, b = client_factory(), client_factory()
    a.join(), b.join()
    sa, sb = server.world.snakes[a.pid], server.world.snakes[b.pid]
    # force known headings so the turn is always legal
    sa.direction = sb.direction = "R"
    a.msg("INPUT", tok=a.tok, seq=1, dir="U")
    pump(server)
    assert sa.pending == "U" and sb.pending is None


def test_input_with_other_players_token_from_wrong_address_is_rejected(server, client_factory):
    a, b = client_factory(), client_factory()
    a.join(), b.join()
    server.world.snakes[a.pid].direction = "R"
    b.msg("INPUT", tok=a.tok, seq=1, dir="U")  # b replays a's token
    pump(server)
    assert server.world.snakes[a.pid].pending is None
    assert any(m["t"] == "ERROR" and m["code"] == P.BAD_SESSION for m in b.recv_all())


def test_duplicate_and_reordered_inputs_ignored(server, client_factory):
    a = client_factory()
    a.join()
    s = server.world.snakes[a.pid]
    s.direction = "R"
    a.msg("INPUT", tok=a.tok, seq=5, dir="U")
    a.msg("INPUT", tok=a.tok, seq=5, dir="U")   # redundant copy
    a.msg("INPUT", tok=a.tok, seq=3, dir="D")   # older, reordered
    pump(server)
    assert s.pending == "U" and server.stats.duplicates == 2


def test_reversal_input_cannot_change_state(server, client_factory):
    a = client_factory()
    a.join()
    s = server.world.snakes[a.pid]
    s.direction = "R"
    a.msg("INPUT", tok=a.tok, seq=1, dir="L")
    pump(server)
    assert s.pending is None


def test_malformed_traffic_rejected_and_server_survives(server, client_factory):
    a = client_factory()
    a.join()
    junk = [b"", b"\x00\xff", b"{", b'{"v":1,"t":"INPUT"}', b'{"v":9,"t":"JOIN","name":"x"}',
            b'{"v":1,"t":"BOOM"}', b"A" * 5000, b'{"v":1,"t":"INPUT","tok":"zzzzzzzzzzzzzzzz","seq":1,"dir":"U"}']
    for j in junk:
        a.send(j)
    pump(server, 5)
    assert server.stats.rejected >= 6
    errors = [m for m in a.recv_all() if m["t"] == "ERROR"]
    assert errors and len(errors) <= P.MAX_S2C_BYTES  # replies are bounded by the error budget
    # still fully operational afterwards
    b = client_factory()
    assert b.join("ok")["pid"]
    assert a.pid in server.world.snakes


def test_error_replies_rate_limited_per_source(server, client_factory):
    a = client_factory()
    for _ in range(50):
        a.send(b"garbage")
    pump(server, 5)
    assert len(a.recv_all()) <= 5


def test_unknown_session_leave_is_silent(server, client_factory):
    a = client_factory()
    a.msg("LEAVE", tok="0" * 16)
    pump(server)
    assert a.recv_all() == []


def test_leave_removes_player(server, client_factory):
    a = client_factory()
    a.join()
    a.msg("LEAVE", tok=a.tok)
    pump(server)
    assert not server.sessions and a.pid not in server.world.snakes


def test_ping_pong_and_keepalive(server, client_factory):
    a = client_factory()
    a.join()
    a.msg("PING", tok=a.tok, seq=9, ts=1.5)
    pump(server)
    pong = [m for m in a.recv_all() if m["t"] == "PONG"][0]
    assert (pong["seq"], pong["ts"]) == (9, 1.5)


def test_inactive_session_expires():
    server = make_server(session_timeout=0.6)
    try:
        c = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        c.settimeout(0.0)
        c.sendto(P.encode("JOIN", P.C2S, name="idle"), server.address)
        server.pump(0.05)
        assert len(server.sessions) == 1
        deadline = time.monotonic() + 3
        while server.sessions and time.monotonic() < deadline:
            server.pump(0.05)
        assert not server.sessions and not server.world.snakes and server.stats.expired == 1
        msgs = []
        while True:
            try:
                msgs.append(P.decode(c.recvfrom(4096)[0], P.S2C))
            except (BlockingIOError, TimeoutError):
                break
        assert any(m["t"] == "ERROR" and m["code"] == P.SESSION_EXPIRED for m in msgs)
        c.close()
    finally:
        server.close()


def test_server_full():
    server = make_server(max_players=1)
    try:
        socks = [socket.socket(socket.AF_INET, socket.SOCK_DGRAM) for _ in range(2)]
        for s in socks:
            s.settimeout(0.0)
            s.sendto(P.encode("JOIN", P.C2S, name="x"), server.address)
        server.pump(0.05)
        replies = [P.decode(socks[1].recvfrom(4096)[0], P.S2C)]
        assert replies[0]["code"] == P.SERVER_FULL and len(server.sessions) == 1
        for s in socks:
            s.close()
    finally:
        server.close()


def test_input_rate_limit(server, client_factory):
    a = client_factory()
    a.join()
    for i in range(1, 200):
        a.msg("INPUT", tok=a.tok, seq=i, dir="U")
    pump(server, 5)
    assert server.stats.rate_limited > 0


def test_port_already_in_use_is_reported_cleanly(server):
    host, port = server.address
    other = SnakeServer(ServerConfig(host=host, port=port))
    with pytest.raises(ServerStartError, match="cannot bind"):
        other.open()


def test_shutdown_releases_socket_and_notifies_clients():
    server = make_server()
    host, port = server.address
    peer = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    peer.settimeout(0.0)
    peer.sendto(P.encode("JOIN", P.C2S, name="x"), server.address)
    server.pump(0.05)
    server.close()
    assert server.sock is None
    msgs = []
    while True:
        try:
            msgs.append(P.decode(peer.recvfrom(4096)[0], P.S2C))
        except (BlockingIOError, TimeoutError):
            break
    assert any(m.get("code") == P.SERVER_SHUTDOWN for m in msgs)
    rebound = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rebound.bind((host, port))  # port is free again
    rebound.close()
    peer.close()


def test_server_keeps_ticking_with_many_clients(server, client_factory):
    clients = [client_factory() for _ in range(6)]
    for c in clients:
        c.join()
    start_tick = server.world.tick
    end = time.monotonic() + 0.5
    while time.monotonic() < end:
        for c in clients:
            c.msg("PING", tok=c.tok, seq=1, ts=0.0)
        server.pump(0.01)
    assert server.world.tick - start_tick >= 3  # ~8 Hz * 0.5 s, not starved by traffic
