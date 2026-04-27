from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Literal, Optional

Player = Literal[1, 2]


@dataclass(frozen=True)
class Position:
    row: int
    col: int

    def __post_init__(self) -> None:
        if not isinstance(self.row, int) or not isinstance(self.col, int):
            raise TypeError("Position coordinates must be integers")


@dataclass(frozen=True)
class Checker:
    player: Player
    is_king: bool = False


class Board:
    def __init__(self, grid: list[list[Optional[Checker]]]):
        if not isinstance(grid, list) or not grid:
            raise ValueError("Board grid must be a non-empty list")

        first_row = grid[0]
        if not isinstance(first_row, list) or not first_row:
            raise ValueError("Board rows must be non-empty lists")

        expected_cols = len(first_row)
        normalized_grid: list[list[Optional[Checker]]] = []
        for row in grid:
            if not isinstance(row, list):
                raise TypeError("Board row must be a list")
            if len(row) != expected_cols:
                raise ValueError("Board rows must have the same length")
            normalized_grid.append(list(row))

        self._grid = normalized_grid

    @classmethod
    def empty(cls, rows: int, cols: int) -> Board:
        if rows <= 0 or cols <= 0:
            raise ValueError("Board dimensions must be positive")
        return cls([[None for _ in range(cols)] for _ in range(rows)])

    def clone(self) -> Board:
        return Board([list(row) for row in self._grid])

    def get(self, position: Position) -> Optional[Checker]:
        return self._grid[position.row][position.col]

    def set(self, position: Position, piece: Optional[Checker]) -> None:
        self._grid[position.row][position.col] = piece

    def to_rows(self) -> list[list[Optional[Checker]]]:
        return [list(row) for row in self._grid]

    def __getitem__(self, index: int) -> list[Optional[Checker]]:
        return self._grid[index]

    def __iter__(self) -> Iterator[list[Optional[Checker]]]:
        return iter(self._grid)

    def __len__(self) -> int:
        return len(self._grid)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Board):
            return self._grid == other._grid
        if isinstance(other, list):
            return self._grid == other
        return False

    def __repr__(self) -> str:
        return f"Board(rows={len(self._grid)}, cols={len(self._grid[0])})"
