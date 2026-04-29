from __future__ import annotations

from typing import cast

from checkers.ai.factory import build_checkers_openrouter_provider_chain
from checkers.ai.contracts import CheckersAIMoveProvider
from checkers.ai.models import CheckersAIMoveContext, CheckersAIMoveDecision
from checkers.models import Game
from checkers.services.converters import SerializedBoard, json_to_board
from checkers.services.logic import get_legal_moves_for_player
from checkers.services.move_entry_utils import (
    resolve_checkers_forced_chain_moves as _get_forced_chain_moves,
)
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
