from __future__ import annotations

import json
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
        payload = self._payload(response)

        self.assertEqual(game.current_turn, PLAYER_DARK)
        self.assertEqual(game.light_time_remaining, DEFAULT_PLAYER_TIME_SECONDS - 10)
        self.assertEqual(game.dark_time_remaining, DEFAULT_PLAYER_TIME_SECONDS)

        self.assertEqual(payload["timeRemaining"], DEFAULT_PLAYER_TIME_SECONDS * 1000)
        self.assertEqual(payload["lightTimeRemaining"], (DEFAULT_PLAYER_TIME_SECONDS - 10) * 1000)
        self.assertEqual(payload["darkTimeRemaining"], DEFAULT_PLAYER_TIME_SECONDS * 1000)

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
        second_payload = self._payload(second_move)

        self.assertEqual(game.current_turn, PLAYER_LIGHT)
        self.assertEqual(game.light_time_remaining, DEFAULT_PLAYER_TIME_SECONDS - 10)
        self.assertEqual(game.dark_time_remaining, DEFAULT_PLAYER_TIME_SECONDS - 5)

        self.assertEqual(second_payload["timeRemaining"], (DEFAULT_PLAYER_TIME_SECONDS - 10) * 1000)
        self.assertEqual(second_payload["lightTimeRemaining"], (DEFAULT_PLAYER_TIME_SECONDS - 10) * 1000)
        self.assertEqual(second_payload["darkTimeRemaining"], (DEFAULT_PLAYER_TIME_SECONDS - 5) * 1000)

    def test_timeout_finishes_game_for_current_player_only(self) -> None:
        game = self._create_game()
        fixed_now = timezone.now().replace(microsecond=0)
        self._set_last_move_at(game, fixed_now - timedelta(seconds=DEFAULT_PLAYER_TIME_SECONDS))

        with patch("checkers.services.game_service.timezone.now", return_value=fixed_now):
            response = self.client.get(f"/api/games/{game.id}/")

        self.assertEqual(response.status_code, 200)
        game.refresh_from_db()
        payload = self._payload(response)

        self.assertEqual(game.status, GAME_STATUS_FINISHED)
        self.assertEqual(game.winner, PLAYER_DARK)
        self.assertEqual(game.light_time_remaining, 0)
        self.assertEqual(game.dark_time_remaining, DEFAULT_PLAYER_TIME_SECONDS)

        self.assertEqual(payload["status"], GAME_STATUS_FINISHED)
        self.assertEqual(payload["winner"], PLAYER_DARK)
        self.assertEqual(payload["timeRemaining"], 0)
        self.assertEqual(payload["lightTimeRemaining"], 0)
        self.assertEqual(payload["darkTimeRemaining"], DEFAULT_PLAYER_TIME_SECONDS * 1000)

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
        undo_payload = self._payload(undo_response)

        game.refresh_from_db()
        self.assertEqual(game.status, GAME_STATUS_IN_PROGRESS)
        self.assertEqual(game.current_turn, PLAYER_LIGHT)
        self.assertEqual(game.light_time_remaining, DEFAULT_PLAYER_TIME_SECONDS)
        self.assertEqual(game.dark_time_remaining, DEFAULT_PLAYER_TIME_SECONDS)

        self.assertEqual(undo_payload["timeRemaining"], DEFAULT_PLAYER_TIME_SECONDS * 1000)
        self.assertEqual(undo_payload["lightTimeRemaining"], DEFAULT_PLAYER_TIME_SECONDS * 1000)
        self.assertEqual(undo_payload["darkTimeRemaining"], DEFAULT_PLAYER_TIME_SECONDS * 1000)

    def test_undo_reverts_entire_turn_after_multi_capture(self) -> None:
        game = self._create_game()
        initial_board = self._build_multi_capture_board()
        base_now = timezone.now().replace(microsecond=0)

        Game.objects.filter(id=game.id).update(
            board=initial_board,
            current_turn=PLAYER_LIGHT,
            status=GAME_STATUS_IN_PROGRESS,
            winner=None,
            light_time_remaining=DEFAULT_PLAYER_TIME_SECONDS,
            dark_time_remaining=DEFAULT_PLAYER_TIME_SECONDS,
            last_move_at=base_now,
        )
        game.refresh_from_db()

        first_now = base_now + timedelta(seconds=4)
        with patch("checkers.services.game_service.timezone.now", return_value=first_now):
            first_move = self.client.post(
                f"/api/games/{game.id}/move/",
                {"from_row": 5, "from_col": 0, "to_row": 3, "to_col": 2},
                format="json",
            )
        self.assertEqual(first_move.status_code, 200)

        second_now = first_now + timedelta(seconds=3)
        self._set_last_move_at(game, first_now)
        with patch("checkers.services.game_service.timezone.now", return_value=second_now):
            second_move = self.client.post(
                f"/api/games/{game.id}/move/",
                {"from_row": 3, "from_col": 2, "to_row": 1, "to_col": 4},
                format="json",
            )
        self.assertEqual(second_move.status_code, 200)

        game.refresh_from_db()
        self.assertEqual(game.current_turn, PLAYER_DARK)
        self.assertEqual(game.light_time_remaining, DEFAULT_PLAYER_TIME_SECONDS - 7)
        self.assertEqual(game.dark_time_remaining, DEFAULT_PLAYER_TIME_SECONDS)
        self.assertEqual(game.moves.count(), 2)

        undo_response = self.client.post(f"/api/games/{game.id}/undo/", {}, format="json")
        self.assertEqual(undo_response.status_code, 200)
        undo_payload = self._payload(undo_response)

        game.refresh_from_db()
        self.assertEqual(game.current_turn, PLAYER_LIGHT)
        self.assertEqual(game.light_time_remaining, DEFAULT_PLAYER_TIME_SECONDS)
        self.assertEqual(game.dark_time_remaining, DEFAULT_PLAYER_TIME_SECONDS)
        self.assertEqual(game.moves.count(), 0)
        self.assertEqual(game.board, initial_board)

        self.assertEqual(undo_payload["timeRemaining"], DEFAULT_PLAYER_TIME_SECONDS * 1000)
        self.assertEqual(undo_payload["lightTimeRemaining"], DEFAULT_PLAYER_TIME_SECONDS * 1000)
        self.assertEqual(undo_payload["darkTimeRemaining"], DEFAULT_PLAYER_TIME_SECONDS * 1000)

    def test_game_service_error_is_rendered_by_global_exception_handler(self) -> None:
        game = self._create_game()

        response = self.client.post(f"/api/games/{game.id}/undo/", {}, format="json")
        payload = self._payload(response)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(payload, {"error": "No moves to undo"})

    def test_move_history_uses_structured_positions_and_milliseconds(self) -> None:
        game = self._create_game()
        fixed_now = timezone.now().replace(microsecond=0)
        self._set_last_move_at(game, fixed_now - timedelta(seconds=10))

        with patch("checkers.services.game_service.timezone.now", return_value=fixed_now):
            move_response = self.client.post(
                f"/api/games/{game.id}/move/",
                {"fromRow": 5, "fromCol": 0, "toRow": 4, "toCol": 1},
                format="json",
            )
        self.assertEqual(move_response.status_code, 200)

        history_response = self.client.get(f"/api/games/{game.id}/moves/")
        self.assertEqual(history_response.status_code, 200)
        history_payload = self._payload(history_response)

        self.assertEqual(history_payload["gameId"], str(game.id))
        self.assertEqual(len(history_payload["moves"]), 1)

        move = history_payload["moves"][0]
        self.assertEqual(move["fromPos"], {"row": 5, "col": 0})
        self.assertEqual(move["toPos"], {"row": 4, "col": 1})
        self.assertIsNone(move["capturedPos"])
        self.assertEqual(move["timeSpent"], 10_000)

    def _create_game(self) -> Game:
        response = self.client.post("/api/games/", {}, format="json")
        self.assertEqual(response.status_code, 201)
        payload = self._payload(response)
        return Game.objects.get(id=payload["id"])

    def _set_last_move_at(self, game: Game, value) -> None:
        Game.objects.filter(id=game.id).update(last_move_at=value)
        game.refresh_from_db()

    def _build_multi_capture_board(self) -> list[list[dict[str, object] | None]]:
        board: list[list[dict[str, object] | None]] = [[None for _ in range(8)] for _ in range(8)]
        board[5][0] = {"player": PLAYER_LIGHT, "is_king": False}
        board[4][1] = {"player": PLAYER_DARK, "is_king": False}
        board[2][3] = {"player": PLAYER_DARK, "is_king": False}
        board[0][1] = {"player": PLAYER_DARK, "is_king": False}
        return board

    def _payload(self, response) -> dict:
        response.render()
        return json.loads(response.content)
