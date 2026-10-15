"""Pure, deterministic game simulation (no sockets, no pygame).

The server owns one ``World``. Clients never run this; they only render the snapshots.

Rules
-----
* Grid arena, one cell per tick per snake. Origin (0, 0) is top-left, y grows downward.
* Direction changes that reverse the snake (U<->D, L<->R) are ignored.
* Eating food: +10 score and +1 length (until ``max_length``).
* Death: leaving the arena, hitting any snake body (including your own), or a
  head-on collision (both heads on the same cell -> both die). Moves are simultaneous,
  and a cell vacated by a tail this tick may be entered.
* A dead snake turns every second segment into food, and respawns after
  ``respawn_ticks`` with score 0.
Known limitations: simultaneous moves mean two heads swapping cells do not collide.
"""
from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field

Cell = tuple[int, int]

DELTAS: dict[str, Cell] = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}
OPPOSITE = {"U": "D", "D": "U", "L": "R", "R": "L"}
_CELL_TO_DIR = {v: k for k, v in DELTAS.items()}
FOOD_SCORE = 10


@dataclass
class Snake:
    pid: int
    name: str
    color: int
    body: deque[Cell] = field(default_factory=deque)  # head first
    direction: str = "R"        # direction of the last executed move
    pending: str | None = None  # validated direction to apply on the next step
    alive: bool = False
    score: int = 0
    deaths: int = 0
    respawn_tick: int = 0


def encode_body(body: deque[Cell] | list[Cell]) -> tuple[int, int, str]:
    """Compact body encoding: head (x, y) plus one U/D/L/R char per step towards the tail."""
    cells = list(body)
    dirs = "".join(
        _CELL_TO_DIR[(b[0] - a[0], b[1] - a[1])] for a, b in zip(cells, cells[1:])
    )
    return cells[0][0], cells[0][1], dirs


def decode_body(x: int, y: int, dirs: str) -> list[Cell]:
    cells = [(x, y)]
    for ch in dirs:
        dx, dy = DELTAS[ch]
        x, y = x + dx, y + dy
        cells.append((x, y))
    return cells


class World:
    def __init__(
        self,
        width: int = 60,
        height: int = 40,
        food_target: int = 30,
        respawn_ticks: int = 36,
        initial_length: int = 3,
        max_length: int = 40,
        rng: random.Random | None = None,
    ) -> None:
        self.width, self.height = width, height
        self.food_target = food_target
        self.respawn_ticks = respawn_ticks
        self.initial_length = initial_length
        self.max_length = max_length
        self.rng = rng or random.Random()
        self.tick = 0
        self.snakes: dict[int, Snake] = {}
        self.food: set[Cell] = set()
        self._top_up_food()

    # ------------------------------------------------------------------ players
    def add_player(self, pid: int, name: str) -> Snake:
        snake = Snake(pid=pid, name=name, color=pid % 8)
        self.snakes[pid] = snake
        self._spawn(snake)
        return snake

    def remove_player(self, pid: int) -> None:
        self.snakes.pop(pid, None)

    def set_direction(self, pid: int, direction: str) -> bool:
        """Validate and queue a direction. Returns False if the input is not allowed."""
        snake = self.snakes.get(pid)
        if snake is None or not snake.alive or direction not in DELTAS:
            return False
        if direction == OPPOSITE[snake.direction]:
            return False
        snake.pending = direction
        return True

    # ------------------------------------------------------------------ simulation
    def step(self) -> list[tuple[int, str]]:
        """Advance one tick. Returns [(pid, reason)] for snakes that died this tick."""
        self.tick += 1
        alive = [s for s in self.snakes.values() if s.alive]

        for s in alive:
            if s.pending:
                s.direction, s.pending = s.pending, None
            dx, dy = DELTAS[s.direction]
            hx, hy = s.body[0]
            s.body.appendleft((hx + dx, hy + dy))
            if s.body[0] in self.food:
                self.food.discard(s.body[0])
                s.score += FOOD_SCORE
                if len(s.body) <= self.max_length:
                    continue  # keep the tail: the snake grows by one
            s.body.pop()

        body_cells: set[Cell] = set()
        head_count: dict[Cell, int] = {}
        for s in alive:
            body_cells.update(list(s.body)[1:])
            head_count[s.body[0]] = head_count.get(s.body[0], 0) + 1

        deaths: list[tuple[int, str]] = []
        for s in alive:
            hx, hy = s.body[0]
            if not (0 <= hx < self.width and 0 <= hy < self.height):
                deaths.append((s.pid, "wall"))
            elif s.body[0] in body_cells:
                deaths.append((s.pid, "body"))
            elif head_count[s.body[0]] > 1:
                deaths.append((s.pid, "head"))
        for pid, _ in deaths:
            self._kill(self.snakes[pid])

        for s in self.snakes.values():
            if not s.alive and self.tick >= s.respawn_tick:
                self._spawn(s)
        self._top_up_food()
        return deaths

    def snapshot(self) -> tuple[list[dict], list[list[int]]]:
        """Authoritative state in wire format (``snakes`` and ``food`` of a STATE message)."""
        snakes = []
        for s in sorted(self.snakes.values(), key=lambda s: s.pid):
            entry: dict = {"id": s.pid, "n": s.name, "c": s.color, "a": int(s.alive), "s": s.score}
            if s.alive:
                entry["x"], entry["y"], entry["d"] = encode_body(s.body)
            snakes.append(entry)
        return snakes, [list(c) for c in sorted(self.food)]

    # ------------------------------------------------------------------ internals
    def _occupied(self) -> set[Cell]:
        return {c for s in self.snakes.values() if s.alive for c in s.body}

    def _kill(self, s: Snake) -> None:
        cells = [c for c in list(s.body)[::2] if 0 <= c[0] < self.width and 0 <= c[1] < self.height]
        for c in cells:
            if len(self.food) < self.food_target + 10:
                self.food.add(c)
        s.body.clear()
        s.alive = False
        s.score = 0
        s.pending = None
        s.deaths += 1
        s.respawn_tick = self.tick + self.respawn_ticks

    def _spawn(self, s: Snake) -> bool:
        occupied = self._occupied()
        n = self.initial_length
        for _ in range(200):
            d = self.rng.choice("UDLR")
            dx, dy = DELTAS[d]
            margin = n + 2
            x = self.rng.randrange(margin, self.width - margin)
            y = self.rng.randrange(margin, self.height - margin)
            cells = [(x - dx * i, y - dy * i) for i in range(n)]  # head first, tail behind
            ahead = (x + dx, y + dy)
            if any(c in occupied or c in self.food for c in cells) or ahead in occupied:
                continue
            s.body = deque(cells)
            s.direction, s.pending, s.alive = d, None, True
            return True
        return False  # arena too crowded; retried next tick

    def _top_up_food(self) -> None:
        occupied = self._occupied()
        attempts = 0
        while len(self.food) < self.food_target and attempts < 100:
            attempts += 1
            c = (self.rng.randrange(self.width), self.rng.randrange(self.height))
            if c not in occupied:
                self.food.add(c)
