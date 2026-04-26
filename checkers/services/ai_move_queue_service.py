from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import django_rq
from redis.exceptions import RedisError
from rq.exceptions import NoSuchJobError
from rq.job import Job

from checkers.background_tasks.ai_move_task import execute_checkers_ai_move_task
from checkers.models import Game
from checkers.services.game_service import GameServiceError


@dataclass(frozen=True)
class CheckersAIMoveEnqueueResult:
    job_id: str
    status: str
    ai_request_id: str


@dataclass(frozen=True)
class CheckersAIMoveJobStatus:
    job_id: str
    status: str
    is_finished: bool
    is_failed: bool
    result: dict[str, object] | None
    error: str | None


def enqueue_checkers_ai_move_task(
    game_id: UUID,
    difficulty: str,
    ai_request_id: str | None = None,
) -> CheckersAIMoveEnqueueResult:
    _ensure_game_exists(game_id)
    normalized_ai_request_id = _normalize_ai_request_id(ai_request_id)
    resolved_ai_request_id = normalized_ai_request_id or f"ai-{uuid4().hex}"

    try:
        queue = django_rq.get_queue("default")
        job = queue.enqueue(
            execute_checkers_ai_move_task,
            game_id=str(game_id),
            difficulty=difficulty,
            ai_request_id=resolved_ai_request_id,
        )
    except RedisError as error:
        raise GameServiceError("AI queue unavailable", status_code=503) from error

    return CheckersAIMoveEnqueueResult(
        job_id=job.id,
        status=job.get_status(refresh=False),
        ai_request_id=resolved_ai_request_id,
    )


def get_checkers_ai_move_task_status(game_id: UUID, job_id: str) -> CheckersAIMoveJobStatus:
    try:
        connection = django_rq.get_connection("default")
        job = Job.fetch(job_id, connection=connection)
    except RedisError as error:
        raise GameServiceError("AI queue unavailable", status_code=503) from error
    except NoSuchJobError as error:
        raise GameServiceError("AI job not found", status_code=404) from error

    _ensure_job_matches_game(game_id, job)

    result = _extract_job_result(job.result)
    error_message = _extract_error_message(job.exc_info)
    status = job.get_status(refresh=False)

    return CheckersAIMoveJobStatus(
        job_id=job.id,
        status=status,
        is_finished=job.is_finished,
        is_failed=job.is_failed,
        result=result,
        error=error_message,
    )


def _ensure_game_exists(game_id: UUID) -> None:
    if not Game.objects.filter(id=game_id).exists():
        raise GameServiceError("Game not found", status_code=404)


def _normalize_ai_request_id(ai_request_id: str | None) -> str | None:
    if ai_request_id is None:
        return None

    cleaned = ai_request_id.strip()
    if not cleaned:
        return None
    return cleaned


def _ensure_job_matches_game(game_id: UUID, job: Job) -> None:
    job_game_id = _extract_job_game_id(job)
    if job_game_id != str(game_id):
        raise GameServiceError("AI job not found", status_code=404)


def _extract_job_game_id(job: Job) -> str | None:
    game_id_obj = job.kwargs.get("game_id")
    if isinstance(game_id_obj, str):
        return game_id_obj

    if len(job.args) > 0 and isinstance(job.args[0], str):
        return job.args[0]

    return None


def _extract_job_result(job_result: object) -> dict[str, object] | None:
    if job_result is None:
        return None

    if isinstance(job_result, dict):
        payload: dict[str, object] = {}
        for key, value in job_result.items():
            if isinstance(key, str):
                payload[key] = value
        return payload

    return {"value": str(job_result)}


def _extract_error_message(exc_info: str | None) -> str | None:
    if exc_info is None:
        return None

    lines = [line.strip() for line in exc_info.splitlines() if line.strip()]
    if not lines:
        return None
    return lines[-1]
