from __future__ import annotations

from uuid import UUID

from checkers.services.game_service import make_ai_move


def execute_checkers_ai_move_task(
    game_id: str,
    difficulty: str,
    ai_request_id: str,
) -> dict[str, object]:
    return make_ai_move(
        game_id=UUID(game_id),
        difficulty=difficulty,
        ai_request_id=ai_request_id,
    )
