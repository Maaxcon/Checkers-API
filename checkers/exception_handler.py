from __future__ import annotations

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from checkers.services.game_service import GameServiceError


def custom_exception_handler(exc: Exception, context: dict[str, object]) -> Response | None:
    response = drf_exception_handler(exc, context)
    if isinstance(exc, GameServiceError):
        return Response(exc.to_payload(), status=exc.status_code)
    return response
