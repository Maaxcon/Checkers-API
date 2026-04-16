from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializers import MoveRequestSerializer
from .services.game_service import (
    GameServiceError,
    create_game as create_game_service,
    get_game as get_game_service,
    get_move_history as get_move_history_service,
    make_move as make_move_service,
    restart_game as restart_game_service,
    undo_move as undo_move_service,
)


def _service_error_response(error: GameServiceError) -> Response:
    return Response(error.to_payload(), status=error.status_code)


@api_view(["POST"])
def create_game(request):
    try:
        payload = create_game_service()
        return Response(payload, status=status.HTTP_201_CREATED)
    except GameServiceError as error:
        return _service_error_response(error)


@api_view(["GET"])
def get_game(request, game_id):
    try:
        payload = get_game_service(game_id)
        return Response(payload, status=status.HTTP_200_OK)
    except GameServiceError as error:
        return _service_error_response(error)


@api_view(["POST"])
def make_move(request, game_id):
    serializer = MoveRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        payload = make_move_service(game_id, **serializer.validated_data)
        return Response(payload, status=status.HTTP_200_OK)
    except GameServiceError as error:
        return _service_error_response(error)


@api_view(["POST"])
def undo_move(request, game_id):
    try:
        payload = undo_move_service(game_id)
        return Response(payload, status=status.HTTP_200_OK)
    except GameServiceError as error:
        return _service_error_response(error)


@api_view(["POST"])
def restart_game(request, game_id):
    try:
        payload = restart_game_service(game_id)
        return Response(payload, status=status.HTTP_200_OK)
    except GameServiceError as error:
        return _service_error_response(error)


@api_view(["GET"])
def get_move_history(request, game_id):
    try:
        payload = get_move_history_service(game_id)
        return Response(payload, status=status.HTTP_200_OK)
    except GameServiceError as error:
        return _service_error_response(error)
