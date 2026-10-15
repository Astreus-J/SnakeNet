"""SnakeNet application protocol v1 (see docs/PROTOCOL.md)."""
from .codec import decode, encode
from .errors import *  # noqa: F401,F403 - error codes and ProtocolError
from .errors import ProtocolError
from .limits import DIRECTIONS, MAX_C2S_BYTES, MAX_S2C_BYTES, NAME_MAX, PROTOCOL_VERSION
from .schemas import C2S, S2C, SCHEMAS

__all__ = ["decode", "encode", "ProtocolError", "DIRECTIONS", "MAX_C2S_BYTES", "MAX_S2C_BYTES",
           "NAME_MAX", "PROTOCOL_VERSION", "C2S", "S2C", "SCHEMAS"]
