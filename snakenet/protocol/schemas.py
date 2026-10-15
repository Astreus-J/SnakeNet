"""Message schemas: type -> (direction, {field: (validator, required)})."""
from __future__ import annotations

from typing import Any

from .limits import DIRECTIONS, NAME_MAX
from .validators import Validator, _enum, _food, _int, _num, _snakes, _text, _token

C2S = "c2s"  # client -> server
S2C = "s2c"  # server -> client

# type -> (direction, {field: (validator, required)})
SCHEMAS: dict[str, tuple[str, dict[str, tuple[Validator, bool]]]] = {
    "JOIN": (C2S, {"name": (_text(1, NAME_MAX), True)}),
    "WELCOME": (S2C, {
        "pid": (_int(1, 2**31), True),
        "tok": (_token, True),
        "w": (_int(8, 512), True),
        "h": (_int(8, 512), True),
        "tick_rate": (_num(1, 240), True),
        "timeout": (_num(0.5, 3600), True),
    }),
    "INPUT": (C2S, {
        "tok": (_token, True),
        "seq": (_int(0, 2**31), True),
        "dir": (_enum(*DIRECTIONS), True),
    }),
    "STATE": (S2C, {
        "seq": (_int(0, 2**53), True),
        "tick": (_int(0, 2**53), True),
        "snakes": (_snakes, True),
        "food": (_food, True),
    }),
    "PING": (C2S, {"tok": (_token, True), "seq": (_int(0, 2**31), True), "ts": (_num(0, 1e12), True)}),
    "PONG": (S2C, {"seq": (_int(0, 2**31), True), "ts": (_num(0, 1e12), True), "tick": (_int(0, 2**53), True)}),
    "LEAVE": (C2S, {"tok": (_token, True)}),
    "ERROR": (S2C, {
        "code": (_text(1, 32), True),
        "msg": (_text(0, 120), True),
        "ref": (_text(0, 16), False),
    }),
}
