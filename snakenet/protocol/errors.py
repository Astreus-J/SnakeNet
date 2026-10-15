"""Error codes carried by ERROR messages, and the exception for malformed datagrams."""
from __future__ import annotations

# Error codes carried by ERROR messages (and by ProtocolError locally).
BAD_JSON = "BAD_JSON"
BAD_VERSION = "BAD_VERSION"
BAD_TYPE = "BAD_TYPE"
BAD_FIELD = "BAD_FIELD"
TOO_LARGE = "TOO_LARGE"
BAD_SESSION = "BAD_SESSION"
SERVER_FULL = "SERVER_FULL"
RATE_LIMITED = "RATE_LIMITED"
SESSION_EXPIRED = "SESSION_EXPIRED"
SERVER_SHUTDOWN = "SERVER_SHUTDOWN"


class ProtocolError(Exception):
    """A datagram violated the protocol. ``code`` is one of the error codes above."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail
