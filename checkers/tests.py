from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from checkers.constants import (
    DEFAULT_PLAYER_TIME_SECONDS,
    GAME_STATUS_FINISHED,
    GAME_STATUS_IN_PROGRESS,
    PLAYER_DARK,
    PLAYER_LIGHT,
)
from checkers.models import Game


class GameTimerTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()

    def test_make_move_decrements_only_current_player_timer(self) -> None:
        game = self._create_game()
        fixed_now = timezone.now().replace(microsecond=0)
        self._set_last_move_at(game, fixed_now - timedelta(seconds=10))

        with patch("checkers.services.game_service.timezone.now", return_value=fixed_now):
            response = self.client.post(
                f"/api/games/{game.id}/move/",
                {"from_row": 5, "from_col": 0, "to_row": 4, "to_col": 1},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        game.refresh_from_db()

        self.assertEqual(game.current_turn, PLAYER_DARK)
        self.assertEqual(game.light_time_remaining, DEFAULT_PLAYER_TIME_SECONDS - 10)
        self.assertEqual(game.dark_time_remaining, DEFAULT_PLAYER_TIME_SECONDS)

        self.assertEqual(response.data["time_remaining"], DEFAULT_PLAYER_TIME_SECONDS)
        self.assertEqual(response.data["light_time_remaining"], DEFAULT_PLAYER_TIME_SECONDS - 10)
        self.assertEqual(response.data["dark_time_remaining"], DEFAULT_PLAYER_TIME_SECONDS)

    def test_dark_move_uses_dark_timer_and_keeps_light_timer(self) -> None:
        game = self._create_game()
        first_now = timezone.now().replace(microsecond=0)

        self._set_last_move_at(game, first_now - timedelta(seconds=10))
        with patch("checkers.services.game_service.timezone.now", return_value=first_now):
            first_move = self.client.post(
                f"/api/games/{game.id}/move/",
                {"from_row": 5, "from_col": 0, "to_row": 4, "to_col": 1},
                format="json",
            )
        self.assertEqual(first_move.status_code, 200)

        second_now = first_now + timedelta(seconds=5)
        self._set_last_move_at(game, first_now)
        with patch("checkers.services.game_service.timezone.now", return_value=second_now):
            second_move = self.client.post(
                f"/api/games/{game.id}/move/",
                {"from_row": 2, "from_col": 1, "to_row": 3, "to_col": 0},
                format="json",
            )

        self.assertEqual(second_move.status_code, 200)
        game.refresh_from_db()

        self.assertEqual(game.current_turn, PLAYER_LIGHT)
        self.assertEqual(game.light_time_remaining, DEFAULT_PLAYER_TIME_SECONDS - 10)
        self.assertEqual(game.dark_time_remaining, DEFAULT_PLAYER_TIME_SECONDS - 5)

        self.assertEqual(second_move.data["time_remaining"], DEFAULT_PLAYER_TIME_SECONDS - 10)
        self.assertEqual(second_move.data["light_time_remaining"], DEFAULT_PLAYER_TIME_SECONDS - 10)
        self.assertEqual(second_move.data["dark_time_remaining"], DEFAULT_PLAYER_TIME_SECONDS - 5)

    def test_timeout_finishes_game_for_current_player_only(self) -> None:
        game = self._create_game()
        fixed_now = timezone.now().replace(microsecond=0)
        self._set_last_move_at(game, fixed_now - timedelta(seconds=DEFAULT_PLAYER_TIME_SECONDS))

        with patch("checkers.services.game_service.timezone.now", return_value=fixed_now):
            response = self.client.get(f"/api/games/{game.id}/")

        self.assertEqual(response.status_code, 200)
        game.refresh_from_db()

        self.assertEqual(game.status, GAME_STATUS_FINISHED)
        self.assertEqual(game.winner, PLAYER_DARK)
        self.assertEqual(game.light_time_remaining, 0)
        self.assertEqual(game.dark_time_remaining, DEFAULT_PLAYER_TIME_SECONDS)

        self.assertEqual(response.data["status"], GAME_STATUS_FINISHED)
        self.assertEqual(response.data["winner"], PLAYER_DARK)
        self.assertEqual(response.data["time_remaining"], 0)
        self.assertEqual(response.data["light_time_remaining"], 0)
        self.assertEqual(response.data["dark_time_remaining"], DEFAULT_PLAYER_TIME_SECONDS)

    def test_undo_restores_time_for_player_who_moved(self) -> None:
        game = self._create_game()
        fixed_now = timezone.now().replace(microsecond=0)
        self._set_last_move_at(game, fixed_now - timedelta(seconds=12))

        with patch("checkers.services.game_service.timezone.now", return_value=fixed_now):
            move_response = self.client.post(
                f"/api/games/{game.id}/move/",
                {"from_row": 5, "from_col": 0, "to_row": 4, "to_col": 1},
                format="json",
            )
        self.assertEqual(move_response.status_code, 200)

        undo_response = self.client.post(f"/api/games/{game.id}/undo/", {}, format="json")
        self.assertEqual(undo_response.status_code, 200)

        game.refresh_from_db()
        self.assertEqual(game.status, GAME_STATUS_IN_PROGRESS)
        self.assertEqual(game.current_turn, PLAYER_LIGHT)
        self.assertEqual(game.light_time_remaining, DEFAULT_PLAYER_TIME_SECONDS)
        self.assertEqual(game.dark_time_remaining, DEFAULT_PLAYER_TIME_SECONDS)

        self.assertEqual(undo_response.data["time_remaining"], DEFAULT_PLAYER_TIME_SECONDS)
        self.assertEqual(undo_response.data["light_time_remaining"], DEFAULT_PLAYER_TIME_SECONDS)
        self.assertEqual(undo_response.data["dark_time_remaining"], DEFAULT_PLAYER_TIME_SECONDS)

    def test_game_service_error_is_rendered_by_global_exception_handler(self) -> None:
        game = self._create_game()

        response = self.client.post(f"/api/games/{game.id}/undo/", {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "No moves to undo"})

    def _create_game(self) -> Game:
        response = self.client.post("/api/games/", {}, format="json")
        self.assertEqual(response.status_code, 201)
        return Game.objects.get(id=response.data["id"])

    def _set_last_move_at(self, game: Game, value) -> None:
        Game.objects.filter(id=game.id).update(last_move_at=value)
        game.refresh_from_db()
