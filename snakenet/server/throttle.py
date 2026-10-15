"""Abuse/noise limiters: per-address ERROR reply budget and de-duplicated logging."""
from __future__ import annotations

import logging

LOG_THROTTLE_SECONDS = 5.0
_MAX_ENTRIES = 1024  # bound memory against spoofed-source floods


class ErrorBudget:
    """Allow at most `per_second` ERROR replies per source address (limits reflection)."""

    def __init__(self, per_second: int = 5) -> None:
        self.per_second = per_second
        self._windows: dict[tuple[str, int], list[float]] = {}

    def allow(self, addr: tuple[str, int], now: float) -> bool:
        if len(self._windows) > _MAX_ENTRIES:
            self._windows.clear()
        window = self._windows.setdefault(addr, [now, 0])
        if now - window[0] >= 1.0:
            window[0], window[1] = now, 0
        if window[1] >= self.per_second:
            return False
        window[1] += 1
        return True


class ThrottledLog:
    """Log at most one line per key every LOG_THROTTLE_SECONDS, reporting the suppressed count."""

    def __init__(self, log: logging.Logger) -> None:
        self._log = log
        self._last: dict[object, tuple[float, int]] = {}

    def warn(self, now: float, key: object, fmt: str, *args: object, exc_info: bool = False) -> None:
        last, suppressed = self._last.get(key, (-1e9, 0))
        if now - last < LOG_THROTTLE_SECONDS:
            self._last[key] = (last, suppressed + 1)
            return
        if len(self._last) > _MAX_ENTRIES:
            self._last.clear()
        self._last[key] = (now, 0)
        suffix = f" (+{suppressed} similar suppressed)" if suppressed else ""
        self._log.warning(fmt + suffix, *args, exc_info=exc_info)
