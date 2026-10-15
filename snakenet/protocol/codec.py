"""encode()/decode(): the only place bytes become validated messages."""
from __future__ import annotations

import json
from typing import Any

from . import errors as E
from .limits import MAX_C2S_BYTES, MAX_S2C_BYTES, PROTOCOL_VERSION
from .schemas import C2S, SCHEMAS

def encode(msg_type: str, direction: str, **fields: Any) -> bytes:
    """Serialize a message. Raises E.ProtocolError(E.TOO_LARGE) if it exceeds the size limit."""
    if msg_type not in SCHEMAS or SCHEMAS[msg_type][0] != direction:
        raise ValueError(f"{msg_type} is not a {direction} message")
    data = json.dumps({"v": PROTOCOL_VERSION, "t": msg_type, **fields}, separators=(",", ":")).encode()
    limit = MAX_C2S_BYTES if direction == C2S else MAX_S2C_BYTES
    if len(data) > limit:
        raise E.ProtocolError(E.TOO_LARGE, f"{len(data)} bytes > {limit}")
    return data


def _reject_constant(name: str) -> Any:
    raise ValueError(f"non-finite number {name}")


def decode(data: bytes, direction: str) -> dict[str, Any]:
    """Parse and validate a datagram that was SENT in ``direction``.

    The server decodes with ``C2S`` and the client with ``S2C``; a message of the wrong
    direction is E.BAD_TYPE, so a client can never be tricked by a forged "C2S" type, etc.
    Returns a dict containing only ``v``, ``t`` and the schema's known fields.
    Raises ProtocolError on any violation (never any other exception).
    """
    limit = MAX_C2S_BYTES if direction == C2S else MAX_S2C_BYTES
    if len(data) > limit:
        raise E.ProtocolError(E.TOO_LARGE, f"{len(data)} bytes > {limit}")
    try:
        obj = json.loads(data.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise E.ProtocolError(E.BAD_JSON, "datagram is not valid UTF-8 JSON") from exc
    if not isinstance(obj, dict):
        raise E.ProtocolError(E.BAD_JSON, "top-level JSON value must be an object")
    if "v" not in obj:
        raise E.ProtocolError(E.BAD_FIELD, "missing 'v'")
    if obj["v"] != PROTOCOL_VERSION or isinstance(obj["v"], bool):
        raise E.ProtocolError(E.BAD_VERSION, f"unsupported version, server speaks {PROTOCOL_VERSION}")
    msg_type = obj.get("t")
    if not isinstance(msg_type, str) or msg_type not in SCHEMAS or SCHEMAS[msg_type][0] != direction:
        raise E.ProtocolError(E.BAD_TYPE, "unknown or unexpected message type")
    out: dict[str, Any] = {"v": PROTOCOL_VERSION, "t": msg_type}
    for name, (check, required) in SCHEMAS[msg_type][1].items():
        if name not in obj:
            if required:
                raise E.ProtocolError(E.BAD_FIELD, f"{msg_type}: missing '{name}'")
            continue
        try:
            out[name] = check(obj[name])
        except (ValueError, TypeError) as exc:
            raise E.ProtocolError(E.BAD_FIELD, f"{msg_type}.{name}: {exc}") from exc
    return out
