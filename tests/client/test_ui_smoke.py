import os

import pytest

from snakenet.config import ClientConfig, ServerConfig
from snakenet.server import SnakeServer


def test_ui_renders_headless_and_exits_cleanly(tmp_path):
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pytest.importorskip("pygame")
    from snakenet.client.ui import run

    server = SnakeServer(ServerConfig(host="127.0.0.1", port=0, seed=5))
    host, port = server.start_background()
    shot = tmp_path / "frame.png"
    try:
        assert run(ClientConfig(host=host, port=port, name="ui"), max_frames=90, screenshot=str(shot)) == 0
        assert shot.exists() and shot.stat().st_size > 1000
    finally:
        server.shutdown()
