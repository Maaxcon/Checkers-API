from __future__ import annotations

from typing import cast

from checkers.ai.factory import build_checkers_openrouter_provider_chain
from checkers.ai.models import CheckersAIMoveContext, CheckersAIMoveDecision
from checkers.ai.contracts import CheckersAIMoveProvider
from checkers.constants import PLAYER_VALUES
from checkers.models import Game
from checkers.services.converters import SerializedBoard, json_to_board
from checkers.services.logic import get_chain_capture_moves, get_legal_moves_for_player
from checkers.services.types import Board, MoveType, Player


def build_checkers_ai_move_context(game: Game, difficulty: str) -> CheckersAIMoveContext:
    board = json_to_board(cast(SerializedBoard, game.board))
    legal_moves = _resolve_legal_moves_for_ai_turn(game, board)
    decisions = tuple(
        CheckersAIMoveDecision(
            from_row=move.from_row,
            from_col=move.from_col,
            to_row=move.row,
            to_col=move.col,
        )
        for move in legal_moves
    )

    return CheckersAIMoveContext(
        game_id=str(game.id),
        board=board,
        current_turn=cast(Player, game.current_turn),
        difficulty=difficulty,
        legal_moves=decisions,
    )


def choose_checkers_ai_move(
    game: Game,
    difficulty: str,
    provider: CheckersAIMoveProvider | None = None,
) -> CheckersAIMoveDecision:
    context = build_checkers_ai_move_context(game, difficulty)
    selected_provider = provider or build_checkers_openrouter_provider_chain()
    result = selected_provider.choose_move(context)
    return result.decision


def _resolve_legal_moves_for_ai_turn(game: Game, board: Board) -> list[MoveType]:
    forced_chain_moves = _get_forced_chain_moves(game, board)
    if forced_chain_moves is not None:
        return forced_chain_moves

    player = cast(Player, game.current_turn)
    return get_legal_moves_for_player(board, player)


def _get_forced_chain_moves(game: Game, board: Board) -> list[MoveType] | None:
    last_move = game.moves.order_by("-created_at", "-id").first()
    if last_move is None or not last_move.is_jump:
        return None

    mover_player = _extract_player_from_board(cast(SerializedBoard, last_move.board_before), last_move.from_pos)
    if mover_player != game.current_turn:
        return None

    to_row, to_col = _extract_pos(last_move.to_pos)
    if to_row is None or to_col is None:
        return None

    chain_moves = get_chain_capture_moves(board, to_row, to_col)
    return chain_moves or None


def _extract_player_from_board(board_json: SerializedBoard, pos: object) -> Player | None:
    row, col = _extract_pos(pos)
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
        return cast(Player, player)
    return None


def _extract_pos(pos: object) -> tuple[int | None, int | None]:
    if not isinstance(pos, (list, tuple)) or len(pos) != 2:
        return None, None
    if not isinstance(pos[0], int) or not isinstance(pos[1], int):
        return None, None
    return pos[0], pos[1]
