from __future__ import annotations

from uuid import UUID

from checkers.models import Game
from checkers.services.game_service import make_ai_move
from rq import get_current_job


def execute_checkers_ai_move_task(
    game_id: str,
    difficulty: str,
    ai_request_id: str,
) -> dict[str, object]:
    resolved_game_id = UUID(game_id)
    current_job = get_current_job()
    current_job_id = current_job.id if current_job is not None else None
    try:
        return make_ai_move(
            game_id=resolved_game_id,
            difficulty=difficulty,
            ai_request_id=ai_request_id,
        )
    finally:
        filters: dict[str, object] = {"id": resolved_game_id}
        if current_job_id is not None:
            filters["current_ai_job_id"] = current_job_id
        Game.objects.filter(**filters).update(current_ai_job_id=None)
