from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, Union

Player = Literal[1, 2]

@dataclass(frozen=True)
class Piece:
    player: Player
    is_king: bool = False

@dataclass(frozen=True)
class Move:
    from_row: int
    from_col: int
    row: int
    col: int
    type: Literal["move"] = "move"

@dataclass(frozen=True)
class CaptureMove:
    from_row: int
    from_col: int
    row: int
    col: int
    captured_row: int
    captured_col: int
    type: Literal["capture"] = "capture"

MoveType = Union[Move, CaptureMove]
Board = list[list[Optional[Piece]]]
