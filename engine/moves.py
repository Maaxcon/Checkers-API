from __future__ import annotations

from typing import Optional

from .board import get_piece, is_valid_position
from .constants import CAPTURE_DIRS, DIRECTIONS, GAME_SETTINGS, HORIZONTAL_DIRS, PLAYERS
from .types import Board, CaptureMove, Move, MoveType, Piece

def is_opponent(piece: Piece, other: Optional[Piece]) -> bool:
    return other is not None and piece.player != other.player

def get_move_directions(piece: Piece) -> list[int]:
    if piece.is_king:
        return [DIRECTIONS.UP, DIRECTIONS.DOWN]
    return [DIRECTIONS.UP] if piece.player == PLAYERS.LIGHT else [DIRECTIONS.DOWN]

def get_moves_for_piece(board: Board, row: int, col: int) -> list[MoveType]:
    piece = get_piece(board, row, col)
    if piece is None:
        return []
    if piece.is_king:
        return get_king_moves(board, row, col, piece)
    return get_normal_piece_moves(board, row, col, piece)

def get_normal_piece_moves(board: Board, row: int, col: int, piece: Piece) -> list[MoveType]:
    moves: list[MoveType] = []
    directions_y = get_move_directions(piece)

    for direction_y in directions_y:
        for direction_x in HORIZONTAL_DIRS:
            new_row = row + direction_y
            new_col = col + direction_x

            if is_valid_position(new_row, new_col):
                target_piece = get_piece(board, new_row, new_col)
                if target_piece is None:
                    moves.append(Move(from_row=row, from_col=col, row=new_row, col=new_col))

    for row_offset, col_offset in CAPTURE_DIRS:
        jump_row = row + row_offset * GAME_SETTINGS.JUMP_DISTANCE
        jump_col = col + col_offset * GAME_SETTINGS.JUMP_DISTANCE
        middle_row = row + row_offset
        middle_col = col + col_offset

        if not is_valid_position(jump_row, jump_col):
            continue

        middle_piece = get_piece(board, middle_row, middle_col)
        target_piece = get_piece(board, jump_row, jump_col)

        if target_piece is None and is_opponent(piece, middle_piece):
            moves.append(
                CaptureMove(
                    from_col=col,
                    from_row=row,
                    row=jump_row,
                    col=jump_col,
                    captured_row=middle_row,
                    captured_col=middle_col,
                )
            )

    return moves

def get_king_moves(board: Board, row: int, col: int, piece: Piece) -> list[MoveType]:
    moves: list[MoveType] = []

    for row_offset, col_offset in CAPTURE_DIRS:
        current_row = row + row_offset
        current_col = col + col_offset
        found_enemy: Optional[tuple[int, int]] = None

        while is_valid_position(current_row, current_col):
            target_piece = get_piece(board, current_row, current_col)

            if found_enemy is None:
                if target_piece is None:
                    moves.append(Move(from_row=row, from_col=col, row=current_row, col=current_col))
                elif is_opponent(piece, target_piece):
                    found_enemy = (current_row, current_col)
                else:
                    break
            else:
                if target_piece is None:
                    moves.append(
                        CaptureMove(
                            from_row=row,
                            from_col=col,
                            row=current_row,
                            col=current_col,
                            captured_row=found_enemy[0],
                            captured_col=found_enemy[1],
                        )
                    )
                else:
                    break

            current_row += row_offset
            current_col += col_offset

    return moves