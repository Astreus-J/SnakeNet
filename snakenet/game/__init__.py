"""Pure game domain: rules and simulation, no I/O."""
from .world import DELTAS, FOOD_SCORE, OPPOSITE, Snake, World, decode_body, encode_body

__all__ = ["DELTAS", "FOOD_SCORE", "OPPOSITE", "Snake", "World", "decode_body", "encode_body"]
