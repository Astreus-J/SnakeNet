"""Configuration: dataclasses + shared argparse helpers. Environment variables supply defaults."""
from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_PORT = 5000  # UDP


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"      # use 0.0.0.0 to accept LAN clients
    port: int = DEFAULT_PORT
    tick_rate: float = 8.0       # simulation steps per second (fixed timestep)
    snapshot_rate: float = 8.0   # STATE snapshots per second (<= tick_rate)
    session_timeout: float = 5.0  # seconds of silence before a session is expired
    max_players: int = 8
    width: int = 60
    height: int = 40
    food_target: int = 30
    max_length: int = 40
    respawn_ticks: int = 36
    input_rate: float = 30.0     # sustained INPUT messages/second allowed per session
    input_burst: int = 30
    seed: int | None = None

    @classmethod
    def default_host(cls) -> str:
        return _env("SNAKENET_HOST", cls.host)

    @classmethod
    def default_port(cls) -> int:
        return int(_env("SNAKENET_PORT", str(DEFAULT_PORT)))


@dataclass
class ClientConfig:
    host: str = "127.0.0.1"
    port: int = DEFAULT_PORT
    name: str = "player"
    join_attempts: int = 5       # JOIN retries before reporting the server unavailable
    join_interval: float = 0.5
    lost_after: float = 2.0      # seconds without any server datagram -> connection lost
    input_redundancy: int = 2    # identical INPUT copies per key press (loss tolerance)
