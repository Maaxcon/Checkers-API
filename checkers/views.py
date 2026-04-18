from uuid import UUID

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from .serializers import MoveRequestSerializer
from .services.game_service import (
    create_game as create_game_service,
    get_game as get_game_service,
    get_move_history as get_move_history_service,
    make_move as make_move_service,
    restart_game as restart_game_service,
    undo_move as undo_move_service,
)


@api_view(["POST"])
def create_game(_request: Request) -> Response:
    payload = create_game_service()
    return Response(payload, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def get_game(_request: Request, game_id: UUID) -> Response:
    payload = get_game_service(game_id)
    return Response(payload, status=status.HTTP_200_OK)


@api_view(["POST"])
def make_move(_request: Request, game_id: UUID) -> Response:
    serializer = MoveRequestSerializer(data=_request.data)
    serializer.is_valid(raise_exception=True)

    payload = make_move_service(game_id, **serializer.validated_data)
    return Response(payload, status=status.HTTP_200_OK)


@api_view(["POST"])
def undo_move(_request: Request, game_id: UUID) -> Response:
    payload = undo_move_service(game_id)
    return Response(payload, status=status.HTTP_200_OK)


@api_view(["POST"])
def restart_game(_request: Request, game_id: UUID) -> Response:
    payload = restart_game_service(game_id)
    return Response(payload, status=status.HTTP_200_OK)


@api_view(["GET"])
def get_move_history(_request: Request, game_id: UUID) -> Response:
    payload = get_move_history_service(game_id)
    return Response(payload, status=status.HTTP_200_OK)
