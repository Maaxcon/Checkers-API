from __future__ import annotations

from uuid import UUID

from checkers.models import Game
from checkers.services.game_service import make_ai_move


def execute_checkers_ai_move_task(
    game_id: str,
    difficulty: str,
    ai_request_id: str,
) -> dict[str, object]:
    resolved_game_id = UUID(game_id)
    try:
        return make_ai_move(
            game_id=resolved_game_id,
            difficulty=difficulty,
            ai_request_id=ai_request_id,
        )
    finally:
        Game.objects.filter(id=resolved_game_id).update(ai_move_pending=False)
