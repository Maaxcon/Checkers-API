from __future__ import annotations

from checkers.constants import PLAYER_VALUES
from checkers.models import Game
from checkers.services.converters import SerializedBoard
from checkers.services.logic import get_chain_capture_moves
from checkers.services.types import Board, MoveType, Player


def resolve_checkers_forced_chain_moves(game: Game, board: Board) -> list[MoveType] | None:
    last_move = game.moves.order_by("-created_at", "-id").first()
    if last_move is None or not last_move.is_jump:
        return None

    mover_player = extract_checkers_player_from_serialized_board(last_move.board_before, last_move.from_pos)
    if mover_player != game.current_turn:
        return None

    to_row, to_col = extract_checkers_position(last_move.to_pos)
    if to_row is None or to_col is None:
        return None

    chain_moves = get_chain_capture_moves(board, to_row, to_col)
    return chain_moves or None


def extract_checkers_player_from_serialized_board(board_json: SerializedBoard, pos: object) -> Player | None:
    row, col = extract_checkers_position(pos)
    if row is None or col is None:
        return None

    try:
        piece = board_json[row][col]
    except (IndexError, TypeError):
        return None

    if piece is None:
        return None

    player = piece["player"]
    if player in PLAYER_VALUES:
        return player
    return None


def extract_checkers_position(pos: object) -> tuple[int | None, int | None]:
    if not isinstance(pos, (list, tuple)) or len(pos) != 2:
        return None, None
    if not isinstance(pos[0], int) or not isinstance(pos[1], int):
        return None, None
    return pos[0], pos[1]
