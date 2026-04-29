from uuid import UUID

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from checkers.models import Game
from .serializers import AIMoveRequestSerializer, MoveRequestSerializer
from .services.ai_move_queue_service import (
    enqueue_checkers_ai_move_task,
    get_checkers_ai_move_task_status,
)
from .services.game_service import (
    GameServiceError,
    create_game as create_game_service,
    get_game as get_game_service,
    get_move_history as get_move_history_service,
    make_move as make_move_service,
    restart_game as restart_game_service,
    undo_move as undo_move_service,
)


@method_decorator(ensure_csrf_cookie, name='dispatch')
class GameViewSet(viewsets.GenericViewSet):
    queryset = Game.objects.all()
    lookup_value_regex = "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"

    def create(self, _request: Request) -> Response:
        payload = create_game_service()
        return Response(payload, status=status.HTTP_201_CREATED)

    def retrieve(self, _request: Request, pk: str | None = None) -> Response:
        game_id = self._require_game_id(pk)
        payload = get_game_service(game_id)
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def move(self, request: Request, pk: str | None = None) -> Response:
        game_id = self._require_game_id(pk)
        serializer = MoveRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payload = make_move_service(game_id, **serializer.validated_data)
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="ai-move")
    def ai_move(self, request: Request, pk: str | None = None) -> Response:
        game_id = self._require_game_id(pk)
        serializer = AIMoveRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        enqueue_result = enqueue_checkers_ai_move_task(game_id, **serializer.validated_data)
        payload = {
            "job_id": enqueue_result.job_id,
            "status": enqueue_result.status,
            "ai_request_id": enqueue_result.ai_request_id,
        }
        return Response(payload, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["get"], url_path=r"ai-move/status/(?P<job_id>[^/.]+)")
    def ai_move_status(self, _request: Request, pk: str | None = None, job_id: str | None = None) -> Response:
        game_id = self._require_game_id(pk)
        if job_id is None:
            raise GameServiceError("AI job not found", status_code=404)

        job_status = get_checkers_ai_move_task_status(game_id=game_id, job_id=job_id)
        payload: dict[str, object] = {
            "job_id": job_status.job_id,
            "status": job_status.status,
            "is_finished": job_status.is_finished,
            "is_failed": job_status.is_failed,
        }
        if job_status.result is not None:
            payload["result"] = job_status.result
        if job_status.error is not None:
            payload["error"] = job_status.error
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def undo(self, _request: Request, pk: str | None = None) -> Response:
        game_id = self._require_game_id(pk)
        payload = undo_move_service(game_id)
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def restart(self, _request: Request, pk: str | None = None) -> Response:
        game_id = self._require_game_id(pk)
        payload = restart_game_service(game_id)
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def moves(self, _request: Request, pk: str | None = None) -> Response:
        game_id = self._require_game_id(pk)
        payload = get_move_history_service(game_id)
        return Response(payload, status=status.HTTP_200_OK)

    def _require_game_id(self, pk: str | None) -> UUID:
        if pk is None:
            raise GameServiceError("Game not found", status_code=404)
        try:
            return UUID(pk)
        except ValueError as error:
            raise GameServiceError("Game not found", status_code=404) from error
