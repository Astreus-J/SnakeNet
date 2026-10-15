"""Client side: network layer (no pygame), pygame UI, and a headless bot."""
from .network import ClientSnapshot, ConnState, NetClient

__all__ = ["NetClient", "ConnState", "ClientSnapshot"]
