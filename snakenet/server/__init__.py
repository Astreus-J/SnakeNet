"""Authoritative UDP game server."""
from .app import ServerStartError, SnakeServer

__all__ = ["SnakeServer", "ServerStartError"]
