import random
from collections import deque

from snakenet.game import World, decode_body, encode_body


def world(**kw):
    return World(width=20, height=20, food_target=0, rng=random.Random(1), **kw)


def place(w, pid, cells, direction):
    s = w.add_player(pid, f"p{pid}")
    s.body, s.direction, s.pending, s.alive = deque(cells), direction, None, True
    return s


def test_body_codec_roundtrip():
    cells = [(5, 5), (4, 5), (4, 6), (3, 6)]
    assert decode_body(*encode_body(cells)) == cells


def test_moves_one_cell_per_tick():
    w = world()
    s = place(w, 1, [(5, 5), (4, 5), (3, 5)], "R")
    w.step()
    assert list(s.body) == [(6, 5), (5, 5), (4, 5)]


def test_reverse_input_is_rejected_and_valid_turn_is_applied():
    w = world()
    s = place(w, 1, [(5, 5), (4, 5), (3, 5)], "R")
    assert not w.set_direction(1, "L")
    assert not w.set_direction(1, "Z")
    assert w.set_direction(1, "U")
    w.step()
    assert s.body[0] == (5, 4)


def test_input_affects_only_target_player():
    w = world()
    a = place(w, 1, [(5, 5), (4, 5), (3, 5)], "R")
    b = place(w, 2, [(5, 12), (4, 12), (3, 12)], "R")
    w.set_direction(1, "D")
    w.step()
    assert a.body[0] == (5, 6) and b.body[0] == (6, 12)


def test_eating_grows_and_scores():
    w = world()
    s = place(w, 1, [(5, 5), (4, 5), (3, 5)], "R")
    w.food.add((6, 5))
    w.step()
    assert len(s.body) == 4 and s.score == 10 and (6, 5) not in w.food


def test_wall_collision_kills_and_drops_food():
    w = world()
    s = place(w, 1, [(19, 5), (18, 5), (17, 5), (16, 5)], "R")
    assert w.step() == [(1, "wall")]
    assert not s.alive and s.deaths == 1 and w.food


def test_body_and_head_collisions():
    w = world()
    place(w, 1, [(5, 5), (4, 5), (3, 5)], "R")
    place(w, 2, [(6, 4), (6, 3), (6, 2)], "D")  # drives into cell (6, 5) the same tick as p1
    assert sorted(w.step()) == [(1, "head"), (2, "head")]
    w = world()
    place(w, 1, [(5, 5), (4, 5), (3, 5)], "R")
    place(w, 2, [(7, 4), (7, 3), (7, 2)], "D")
    place(w, 3, [(8, 6), (9, 6), (10, 6)], "L")
    w.step()
    # p2 head (7,5) is free; p3 head (7,6) free; nobody dies
    assert all(s.alive for s in w.snakes.values())


def test_hitting_other_snake_body_kills_only_the_hitter():
    w = world()
    place(w, 1, [(5, 10), (4, 10), (3, 10), (2, 10)], "R")
    hitter = place(w, 2, [(4, 9), (4, 8), (4, 7)], "D")  # next cell (4,10) is p1's body
    other = w.snakes[1]
    assert w.step() == [(2, "body")]
    assert other.alive and not hitter.alive


def test_respawn_after_delay_with_score_reset():
    w = world(respawn_ticks=3)
    s = place(w, 1, [(19, 5), (18, 5), (17, 5)], "R")
    s.score = 50
    w.step()
    assert not s.alive and s.score == 0
    for _ in range(3):
        w.step()
    assert s.alive and len(s.body) == 3


def test_food_replenished_to_target():
    w = World(width=20, height=20, food_target=10, rng=random.Random(1))
    assert len(w.food) == 10
    w.food.clear()
    w.step()
    assert len(w.food) == 10


def test_snapshot_wire_format():
    w = world()
    place(w, 1, [(5, 5), (4, 5), (3, 5)], "R")
    snakes, _ = w.snapshot()
    assert snakes[0]["x"] == 5 and snakes[0]["d"] == "LL"
