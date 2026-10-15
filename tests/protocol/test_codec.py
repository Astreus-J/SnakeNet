import json
import pytest

from snakenet import protocol as P

TOK = "0123456789abcdef"


def raw(**kw):
    return json.dumps({"v": 1, **kw}).encode()


def test_roundtrip_input():
    msg = P.decode(P.encode("INPUT", P.C2S, tok=TOK, seq=3, dir="L"), P.C2S)
    assert msg == {"v": 1, "t": "INPUT", "tok": TOK, "seq": 3, "dir": "L"}


@pytest.mark.parametrize("data,code", [
    (b"\xff\xfe", P.BAD_JSON),
    (b"not json", P.BAD_JSON),
    (b"[1,2]", P.BAD_JSON),
    (b'{"v":1,"t":"JOIN","name":NaN}', P.BAD_JSON),
    (b"[" * 900, P.BAD_JSON),
    (json.dumps({"t": "JOIN", "name": "a"}).encode(), P.BAD_FIELD),
    (raw(t="JOIN", name="a").replace(b'"v": 1', b'"v": 2'), P.BAD_VERSION),
    (raw(t="NOPE"), P.BAD_TYPE),
    (raw(t="STATE", seq=1, tick=1, snakes=[], food=[]), P.BAD_TYPE),  # server-only type sent by a client
    (raw(t="JOIN"), P.BAD_FIELD),
    (raw(t="JOIN", name=""), P.BAD_FIELD),
    (raw(t="JOIN", name="x" * 50), P.BAD_FIELD),
    (raw(t="JOIN", name="bad\x00name"), P.BAD_FIELD),
    (raw(t="INPUT", tok=TOK, seq=1, dir="X"), P.BAD_FIELD),
    (raw(t="INPUT", tok=TOK, seq=True, dir="U"), P.BAD_FIELD),
    (raw(t="INPUT", tok=TOK, seq=-1, dir="U"), P.BAD_FIELD),
    (raw(t="INPUT", tok="short", seq=1, dir="U"), P.BAD_FIELD),
    (b"x" * (P.MAX_C2S_BYTES + 1), P.TOO_LARGE),
])
def test_server_rejects(data, code):
    with pytest.raises(P.ProtocolError) as exc:
        P.decode(data, P.C2S)
    assert exc.value.code == code


def test_client_rejects_c2s_type_from_server():
    with pytest.raises(P.ProtocolError) as exc:
        P.decode(P.encode("JOIN", P.C2S, name="a"), P.S2C)
    assert exc.value.code == P.BAD_TYPE


def test_state_validation_rejects_alive_snake_without_body():
    bad = raw(t="STATE", seq=1, tick=1, snakes=[{"id": 1, "n": "a", "c": 0, "a": 1, "s": 0}], food=[])
    with pytest.raises(P.ProtocolError):
        P.decode(bad, P.S2C)


def test_worst_case_state_fits_in_one_unfragmented_datagram():
    snakes = [{"id": i, "n": "n" * 12, "c": i % 8, "a": 1, "s": 99999, "x": 59, "y": 39, "d": "U" * 39}
              for i in range(1, 9)]
    food = [[59, 39]] * 40  # food cap is food_target + 10
    data = P.encode("STATE", P.S2C, seq=2**40, tick=2**40, snakes=snakes, food=food)
    assert len(data) <= P.MAX_S2C_BYTES
    P.decode(data, P.S2C)
