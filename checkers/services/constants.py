from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from .types import Player

@dataclass(frozen=True)
class BoardConfig:
    ROWS: int
    COLS: int
    PIECE_ROWS: int

@dataclass(frozen=True)
class Players:
    LIGHT: Player
    DARK: Player

@dataclass(frozen=True)
class Directions:
    UP: int
    DOWN: int

@dataclass(frozen=True)
class GameSettings:
    JUMP_DISTANCE: int

BOARD: Final[BoardConfig] = BoardConfig(ROWS=8, COLS=8, PIECE_ROWS=3)
PLAYERS: Final[Players] = Players(LIGHT="light", DARK="dark")
DIRECTIONS: Final[Directions] = Directions(UP=-1, DOWN=1)
GAME_SETTINGS: Final[GameSettings] = GameSettings(JUMP_DISTANCE=2)
CAPTURE_DIRS: Final[tuple[tuple[int, int], ...]] = ((-1, -1), (-1, 1), (1, -1), (1, 1))
HORIZONTAL_DIRS: Final[tuple[int, int]] = (-1, 1)
TOP_ROW_INDEX: Final[int] = 0
MIN_INPUT_INDEX: Final[int] = 0
COORD_PARTS_COUNT: Final[int] = 2
DARK_SQUARE_PARITY: Final[int] = 1
MOVE_TYPE_CAPTURE: Final[str] = "capture"
