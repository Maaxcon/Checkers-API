from __future__ import annotations

from typing import Optional

from .constants import BOARD, DARK_SQUARE_PARITY, MIN_INPUT_INDEX, PLAYERS
from .types import Board, Piece

def create_initial_board() -> Board:
    grid: Board = [[None] * BOARD.COLS for _ in range(BOARD.ROWS)]

    for row in range(BOARD.ROWS):
        for col in range(BOARD.COLS):
            if (row + col) % 2 == DARK_SQUARE_PARITY:
                if row < BOARD.PIECE_ROWS:
                    grid[row][col] = Piece(player=PLAYERS.DARK)
                elif row >= BOARD.ROWS - BOARD.PIECE_ROWS:
                    grid[row][col] = Piece(player=PLAYERS.LIGHT)

    return grid

def clone_board(board: Board) -> Board:
    return [list(row) for row in board]

def is_valid_position(row: int, col: int) -> bool:
    return MIN_INPUT_INDEX <= row < BOARD.ROWS and MIN_INPUT_INDEX <= col < BOARD.COLS

def get_piece(board: Board, row: int, col: int) -> Optional[Piece]:
    if not is_valid_position(row, col):
        return None
    return board[row][col]