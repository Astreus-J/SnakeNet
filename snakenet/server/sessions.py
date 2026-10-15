"""Per-player session state and the input rate limiter."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Session:
    pid: int
    token: str
    addr: tuple[str, int]
    name: str
    last_seen: float
    bucket: float          # token bucket: available INPUT credits
    bucket_t: float        # last refill time
    last_input_seq: int = -1

    def allow_input(self, now: float, rate: float, burst: int) -> bool:
        """Token bucket: `rate` inputs/second sustained, up to `burst` at once."""
        self.bucket = min(burst, self.bucket + (now - self.bucket_t) * rate)
        self.bucket_t = now
        if self.bucket < 1.0:
            return False
        self.bucket -= 1.0
        return True

    def accept_input_seq(self, seq: int) -> bool:
        """False for duplicate/reordered datagrams (including deliberate redundant copies)."""
        if seq <= self.last_input_seq:
            return False
        self.last_input_seq = seq
        return True
