"""pygame front-end. Rendering only: all game state comes from server snapshots.

Run:  python -m snakenet.client --host 127.0.0.1 --port 5000 --name ana
"""
from __future__ import annotations

import argparse
import sys

import pygame

from .network import ConnState, NetClient
from ..config import ClientConfig, ServerConfig
from ..game import decode_body

CELL = 16
SIDEBAR = 240
BG = (11, 16, 32)
GRID = (20, 28, 52)
TEXT = (220, 230, 255)
DIM = (120, 135, 170)
FOOD = (255, 206, 86)
PALETTE = [(80, 250, 180), (255, 99, 132), (86, 180, 255), (255, 170, 60),
           (190, 120, 255), (255, 235, 90), (255, 120, 220), (120, 255, 90)]
KEYS = {pygame.K_UP: "U", pygame.K_w: "U", pygame.K_DOWN: "D", pygame.K_s: "D",
        pygame.K_LEFT: "L", pygame.K_a: "L", pygame.K_RIGHT: "R", pygame.K_d: "R"}
STATE_COLOR = {ConnState.CONNECTED: (90, 230, 140), ConnState.JOINING: FOOD, ConnState.LOST: (255, 140, 60),
               ConnState.FAILED: (255, 90, 90), ConnState.CLOSED: DIM}


def run(cfg: ClientConfig, max_frames: int | None = None, screenshot: str | None = None) -> int:
    pygame.init()
    net = NetClient(cfg)
    net.start()
    try:
        # Window size is set after WELCOME; start with the default arena.
        w, h = ServerConfig.width, ServerConfig.height
        screen = pygame.display.set_mode((w * CELL + SIDEBAR, h * CELL))
        pygame.display.set_caption("SnakeNet")
        font, big = pygame.font.Font(None, 22), pygame.font.Font(None, 40)
        clock = pygame.time.Clock()
        frames = 0
        running = True
        while running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                    running = False
                elif ev.type == pygame.KEYDOWN:
                    if ev.key in KEYS:
                        net.send_input(KEYS[ev.key])
                    elif ev.key == pygame.K_r:
                        net.retry()
            snap = net.snapshot()
            if snap.width and (snap.width * CELL + SIDEBAR, snap.height * CELL) != screen.get_size():
                screen = pygame.display.set_mode((snap.width * CELL + SIDEBAR, snap.height * CELL))
            _draw(screen, font, big, snap)
            pygame.display.flip()
            frames += 1
            if max_frames is not None and frames >= max_frames:
                break
            clock.tick(60)
        if screenshot:
            pygame.image.save(screen, screenshot)
    finally:
        net.close()  # sends LEAVE and closes the socket
        pygame.quit()
    return 0


def _draw(screen: pygame.Surface, font: pygame.font.Font, big: pygame.font.Font, snap) -> None:
    screen.fill(BG)
    aw, ah = (snap.width or ServerConfig.width), (snap.height or ServerConfig.height)
    for x in range(0, aw * CELL + 1, CELL):
        pygame.draw.line(screen, GRID, (x, 0), (x, ah * CELL))
    for y in range(0, ah * CELL + 1, CELL):
        pygame.draw.line(screen, GRID, (0, y), (aw * CELL, y))
    view = snap.view
    if view:
        for fx, fy in view["food"]:
            pygame.draw.circle(screen, FOOD, (fx * CELL + CELL // 2, fy * CELL + CELL // 2), CELL // 3)
        for s in view["snakes"]:
            if not s["a"]:
                continue
            color = PALETTE[s["c"] % len(PALETTE)]
            cells = decode_body(s["x"], s["y"], s["d"])
            for i, (cx, cy) in enumerate(reversed(cells)):
                shade = tuple(int(c * (0.55 + 0.45 * (i + 1) / len(cells))) for c in color)
                pygame.draw.rect(screen, shade, (cx * CELL + 1, cy * CELL + 1, CELL - 2, CELL - 2), border_radius=4)
            hx, hy = cells[0]
            rect = (hx * CELL, hy * CELL, CELL, CELL)
            pygame.draw.rect(screen, (255, 255, 255) if s["id"] == snap.pid else color, rect, 2, border_radius=5)
            label = font.render(s["n"], True, TEXT)
            screen.blit(label, (hx * CELL - label.get_width() // 2 + CELL // 2, hy * CELL - 16))
    _sidebar(screen, font, big, snap, aw * CELL)


def _sidebar(screen: pygame.Surface, font: pygame.font.Font, big: pygame.font.Font, snap, x0: int) -> None:
    x, y = x0 + 14, 12
    screen.blit(big.render("SnakeNet", True, PALETTE[0]), (x, y))
    y += 44
    pygame.draw.circle(screen, STATE_COLOR[snap.state], (x + 6, y + 8), 6)
    screen.blit(font.render(snap.state.value.upper(), True, TEXT), (x + 20, y))
    y += 22
    info = [f"player id: {snap.pid or '-'}",
            f"ping: {'-' if snap.rtt_ms is None else f'{snap.rtt_ms:.0f} ms'}",
            f"tick: {snap.view['tick'] if snap.view else '-'}",
            f"rx/tx: {snap.rx}/{snap.tx}  stale: {snap.stale_dropped}"]
    for line in info:
        screen.blit(font.render(line, True, DIM), (x, y))
        y += 20
    y += 10
    screen.blit(font.render("LEADERBOARD", True, TEXT), (x, y))
    y += 24
    if snap.view:
        for rank, s in enumerate(sorted(snap.view["snakes"], key=lambda s: (-s["s"], s["id"]))[:8], 1):
            color = PALETTE[s["c"] % len(PALETTE)] if s["a"] else DIM
            mark = "> " if s["id"] == snap.pid else "  "
            screen.blit(font.render(f"{mark}{rank}. {s['n']}", True, color), (x, y))
            score = font.render(str(s["s"]), True, color)
            screen.blit(score, (x + SIDEBAR - 36 - score.get_width(), y))
            y += 20
    hy = screen.get_height() - 70
    for line in ("Arrows / WASD: move", "R: reconnect   Esc: quit"):
        screen.blit(font.render(line, True, DIM), (x, hy))
        hy += 20
    me = next((s for s in snap.view["snakes"] if s["id"] == snap.pid), None) if snap.view else None
    banner = None
    if snap.state is not ConnState.CONNECTED:
        banner = snap.message
    elif me is not None and not me["a"]:
        banner = "You crashed - respawning..."
    if banner:
        text = big.render(banner[:60], True, STATE_COLOR.get(snap.state, FOOD))
        cx = (x0 - text.get_width()) // 2
        pygame.draw.rect(screen, BG, (cx - 12, 14, text.get_width() + 24, 52), border_radius=8)
        screen.blit(text, (cx, 20))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SnakeNet pygame client")
    ap.add_argument("--host", default=ServerConfig.default_host())
    ap.add_argument("--port", type=int, default=ServerConfig.default_port())
    ap.add_argument("--name", default="player")
    ap.add_argument("--frames", type=int, default=None, help="testing aid: exit after N frames")
    ap.add_argument("--screenshot", default=None, help="testing aid: save last frame to PNG")
    a = ap.parse_args(argv)
    return run(ClientConfig(host=a.host, port=a.port, name=a.name[:12] or "player"), a.frames, a.screenshot)


if __name__ == "__main__":
    sys.exit(main())
