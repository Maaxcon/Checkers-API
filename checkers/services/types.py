from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Union

from .entities import Board, Checker, Player as EntityPlayer, Position

Player = EntityPlayer
Piece = Checker


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
