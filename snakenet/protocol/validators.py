"""Field validators: each returns the cleaned value or raises ValueError."""
from __future__ import annotations

import string
from typing import Any, Callable

from .limits import DIRECTIONS, MAX_BODY_CHARS, MAX_FOOD_IN_STATE, MAX_SNAKES_IN_STATE, NAME_MAX

Validator = Callable[[Any], Any]


def _int(lo: int, hi: int) -> Validator:
    def check(x: Any) -> int:
        # bool is a subclass of int in Python; reject it explicitly.
        if isinstance(x, bool) or not isinstance(x, int) or not lo <= x <= hi:
            raise ValueError(f"expected int in [{lo}, {hi}]")
        return x
    return check


def _num(lo: float, hi: float) -> Validator:
    def check(x: Any) -> float:
        if isinstance(x, bool) or not isinstance(x, (int, float)) or not lo <= x <= hi:
            raise ValueError(f"expected number in [{lo}, {hi}]")
        return x
    return check


def _enum(*allowed: str) -> Validator:
    def check(x: Any) -> str:
        if not isinstance(x, str) or x not in allowed:
            raise ValueError(f"expected one of {allowed}")
        return x
    return check


def _text(min_len: int, max_len: int) -> Validator:
    def check(x: Any) -> str:
        if not isinstance(x, str):
            raise ValueError("expected string")
        x = x.strip()
        if not min_len <= len(x) <= max_len or not x.isprintable():
            raise ValueError(f"expected printable string of {min_len}..{max_len} chars")
        return x
    return check


_HEX = set(string.hexdigits.lower())


def _token(x: Any) -> str:
    if not isinstance(x, str) or len(x) != 16 or not set(x) <= _HEX:
        raise ValueError("expected 16 lowercase hex chars")
    return x


def _dirs(x: Any) -> str:
    if not isinstance(x, str) or len(x) > MAX_BODY_CHARS or not set(x) <= set("UDLR"):
        raise ValueError("expected string of U/D/L/R")
    return x


_snake_fields: dict[str, tuple[Validator, bool]] = {
    "id": (_int(1, 2**31), True),
    "n": (_text(1, NAME_MAX), True),
    "c": (_int(0, 255), True),
    "a": (_int(0, 1), True),
    "s": (_int(0, 10**9), True),
    "x": (_int(-1, 4096), False),
    "y": (_int(-1, 4096), False),
    "d": (_dirs, False),
}


def _snakes(x: Any) -> list[dict]:
    if not isinstance(x, list) or len(x) > MAX_SNAKES_IN_STATE:
        raise ValueError("expected list of snakes")
    out = []
    for item in x:
        if not isinstance(item, dict):
            raise ValueError("snake must be an object")
        clean = {}
        for name, (check, required) in _snake_fields.items():
            if name in item:
                clean[name] = check(item[name])
            elif required:
                raise ValueError(f"snake missing '{name}'")
        if clean["a"] and not {"x", "y", "d"} <= clean.keys():
            raise ValueError("alive snake needs x, y, d")
        out.append(clean)
    return out


def _food(x: Any) -> list[list[int]]:
    if not isinstance(x, list) or len(x) > MAX_FOOD_IN_STATE:
        raise ValueError("expected list of [x, y]")
    cell = _int(0, 4096)
    out = []
    for item in x:
        if not isinstance(item, list) or len(item) != 2:
            raise ValueError("food must be [x, y]")
        out.append([cell(item[0]), cell(item[1])])
    return out
