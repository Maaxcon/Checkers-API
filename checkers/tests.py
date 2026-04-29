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
    PLAYER_VALUES,
)
from checkers.ai.models import CheckersAIMoveContext, CheckersAIMoveDecision
from checkers.ai.models import CheckersAIProviderInvalidResponseError
from checkers.ai.providers import CheckersOpenRouterProvider
from checkers.models import Game
from checkers.services.ai_move_queue_service import CheckersAIMoveEnqueueResult, CheckersAIMoveJobStatus
from checkers.services.game_service import GameServiceError, make_ai_move as make_ai_move_service
from checkers.services.game_service import make_move as make_move_service
from checkers.services.types import Board
from checkers.views import GameViewSet


class _NoopOpenRouterAdapter:
    def create_chat_completion(self, _payload):
        raise AssertionError("create_chat_completion should not be called in payload unit tests")


class GameTimerTests(TestCase):
    FRONTEND_ONLY_HIGHLIGHT_FIELDS = {
        "validMoves",
        "mandatoryPieces",
        "historyHighlight",
        "historyIndex",
        "selected",
        "lastMove",
        "multiJump",
    }

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

    def test_move_on_finished_game_returns_conflict(self) -> None:
        game = self._create_game()
        Game.objects.filter(id=game.id).update(status=GAME_STATUS_FINISHED, winner=PLAYER_DARK)

        response = self.client.post(
            f"/api/games/{game.id}/move/",
            {"from_row": 5, "from_col": 0, "to_row": 4, "to_col": 1},
            format="json",
        )
        payload = self._payload(response)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(payload, {"error": "Game is already finished"})

    def test_require_game_id_returns_not_found_for_malformed_uuid(self) -> None:
        view = GameViewSet()

        with self.assertRaises(GameServiceError) as error_context:
            view._require_game_id("not-a-uuid")

        self.assertEqual(error_context.exception.message, "Game not found")
        self.assertEqual(error_context.exception.status_code, 404)

    def test_api_payloads_do_not_expose_frontend_highlight_fields(self) -> None:
        create_response = self.client.post("/api/games/", {}, format="json")
        self.assertEqual(create_response.status_code, 201)
        create_payload = self._payload(create_response)
        self._assert_no_highlight_fields(create_payload)

        game_id = create_payload["id"]

        retrieve_response = self.client.get(f"/api/games/{game_id}/")
        self.assertEqual(retrieve_response.status_code, 200)
        retrieve_payload = self._payload(retrieve_response)
        self._assert_no_highlight_fields(retrieve_payload)

        move_response = self.client.post(
            f"/api/games/{game_id}/move/",
            {"from_row": 5, "from_col": 0, "to_row": 4, "to_col": 1},
            format="json",
        )
        self.assertEqual(move_response.status_code, 200)
        move_payload = self._payload(move_response)
        self._assert_no_highlight_fields(move_payload)

        history_response = self.client.get(f"/api/games/{game_id}/moves/")
        self.assertEqual(history_response.status_code, 200)
        history_payload = self._payload(history_response)
        self.assertEqual(set(history_payload.keys()), {"gameId", "moveLog"})
        self._assert_no_highlight_fields(history_payload)

    def test_move_history_includes_frontend_style_move_log(self) -> None:
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
        self.assertNotIn("moves", history_payload)
        self.assertEqual(len(history_payload["moveLog"]), 1)

        move_log_entry = history_payload["moveLog"][0]
        self.assertEqual(move_log_entry["notation"], "a3-b4")
        self.assertEqual(move_log_entry["from"], {"row": 5, "col": 0})
        self.assertEqual(move_log_entry["to"], {"row": 4, "col": 1})

    def test_move_history_groups_multi_capture_into_single_move_log_entry(self) -> None:
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

        history_response = self.client.get(f"/api/games/{game.id}/moves/")
        self.assertEqual(history_response.status_code, 200)
        history_payload = self._payload(history_response)

        self.assertNotIn("moves", history_payload)
        self.assertEqual(len(history_payload["moveLog"]), 1)
        self.assertEqual(history_payload["moveLog"][0]["notation"], "a3 x c5xe7")
        self.assertEqual(history_payload["moveLog"][0]["from"], {"row": 5, "col": 0})
        self.assertEqual(history_payload["moveLog"][0]["to"], {"row": 1, "col": 4})

    def test_ai_move_endpoint_enqueues_background_job(self) -> None:
        game = self._create_game()

        with patch(
            "checkers.views.enqueue_checkers_ai_move_task",
            return_value=CheckersAIMoveEnqueueResult(
                job_id="job-123",
                status="queued",
                ai_request_id="ai-job-1",
            ),
        ):
            response = self.client.post(
                f"/api/games/{game.id}/ai-move/",
                {"difficulty": "medium", "aiRequestId": "ai-job-1"},
                format="json",
            )

        self.assertEqual(response.status_code, 202)
        payload = self._payload(response)
        self.assertEqual(payload["jobId"], "job-123")
        self.assertEqual(payload["status"], "queued")
        self.assertEqual(payload["aiRequestId"], "ai-job-1")

    def test_ai_move_endpoint_requires_ai_request_id(self) -> None:
        game = self._create_game()
        response = self.client.post(
            f"/api/games/{game.id}/ai-move/",
            {"difficulty": "medium"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_ai_move_endpoint_rejects_when_ai_move_is_already_pending(self) -> None:
        game = self._create_game()
        Game.objects.filter(id=game.id).update(current_ai_job_id="job-in-progress")

        response = self.client.post(
            f"/api/games/{game.id}/ai-move/",
            {"difficulty": "medium", "aiRequestId": "ai-job-2"},
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        payload = self._payload(response)
        self.assertEqual(payload, {"error": "AI move already in progress"})

    def test_ai_move_status_endpoint_returns_finished_job_payload(self) -> None:
        game = self._create_game()

        base_status = CheckersAIMoveJobStatus(
            job_id="job-777",
            status="finished",
            is_finished=True,
            is_failed=False,
            result={"status": GAME_STATUS_IN_PROGRESS},
            error=None,
        )

        with patch(
            "checkers.views.get_checkers_ai_move_task_status",
            return_value=base_status,
        ):
            response = self.client.get(f"/api/games/{game.id}/ai-move/status/job-777/")

        self.assertEqual(response.status_code, 200)
        payload = self._payload(response)
        self.assertEqual(payload["jobId"], "job-777")
        self.assertEqual(payload["status"], "finished")
        self.assertTrue(payload["isFinished"])
        self.assertFalse(payload["isFailed"])
        self.assertEqual(payload["result"], {"status": GAME_STATUS_IN_PROGRESS})

    def test_make_ai_move_skips_stale_ai_decision_when_state_changed_during_thinking(self) -> None:
        game = self._create_game()
        stale_ai_request_id = "ai-race-1"

        def choose_move_with_concurrent_human_move(*, game, difficulty):
            self.assertEqual(difficulty, "medium")
            make_move_service(
                game_id=game.id,
                from_row=5,
                from_col=0,
                to_row=4,
                to_col=1,
            )
            return CheckersAIMoveDecision(
                from_row=2,
                from_col=1,
                to_row=3,
                to_col=0,
            )

        with patch(
            "checkers.services.game_service.choose_checkers_ai_move",
            side_effect=choose_move_with_concurrent_human_move,
        ):
            make_ai_move_service(
                game_id=game.id,
                difficulty="medium",
                ai_request_id=stale_ai_request_id,
            )

        game.refresh_from_db()
        self.assertEqual(game.moves.count(), 1)
        self.assertFalse(
            game.moves.filter(ai_request_id=stale_ai_request_id).exists(),
            "Stale AI decision must not be applied after board state changed.",
        )

    def test_api_contract_for_all_endpoints(self) -> None:
        create_response = self.client.post("/api/games/", {}, format="json")
        self.assertEqual(create_response.status_code, 201)
        create_payload = self._payload(create_response)
        game_id = create_payload["id"]
        self._assert_game_state_payload(create_payload)
        self.assertEqual(create_payload["status"], GAME_STATUS_IN_PROGRESS)

        get_response = self.client.get(f"/api/games/{game_id}/")
        self.assertEqual(get_response.status_code, 200)
        get_payload = self._payload(get_response)
        self._assert_game_state_payload(get_payload)
        self.assertIn(get_payload["status"], {GAME_STATUS_IN_PROGRESS, GAME_STATUS_FINISHED})

        move_response = self.client.post(
            f"/api/games/{game_id}/move/",
            {"fromRow": 5, "fromCol": 0, "toRow": 4, "toCol": 1},
            format="json",
        )
        self.assertEqual(move_response.status_code, 200)
        move_payload = self._payload(move_response)
        self._assert_game_state_payload(move_payload)
        self.assertIn(move_payload["status"], {GAME_STATUS_IN_PROGRESS, GAME_STATUS_FINISHED})

        undo_response = self.client.post(f"/api/games/{game_id}/undo/", {}, format="json")
        self.assertEqual(undo_response.status_code, 200)
        undo_payload = self._payload(undo_response)
        self._assert_game_state_payload(undo_payload)
        self.assertEqual(undo_payload["status"], GAME_STATUS_IN_PROGRESS)

        restart_response = self.client.post(f"/api/games/{game_id}/restart/", {}, format="json")
        self.assertEqual(restart_response.status_code, 200)
        restart_payload = self._payload(restart_response)
        self._assert_game_state_payload(restart_payload)
        self.assertEqual(restart_payload["status"], GAME_STATUS_IN_PROGRESS)

        history_response = self.client.get(f"/api/games/{game_id}/moves/")
        self.assertEqual(history_response.status_code, 200)
        history_payload = self._payload(history_response)
        self.assertEqual(set(history_payload.keys()), {"gameId", "moveLog"})
        self.assertEqual(history_payload["gameId"], str(game_id))
        self.assertIsInstance(history_payload["moveLog"], list)
        if history_payload["moveLog"]:
            entry = history_payload["moveLog"][0]
            self.assertEqual(set(entry.keys()), {"notation", "from", "to"})
            self.assertIsInstance(entry["notation"], str)
            self.assertEqual(set(entry["from"].keys()), {"row", "col"})
            self.assertEqual(set(entry["to"].keys()), {"row", "col"})

    def _create_game(self) -> Game:
        response = self.client.post("/api/games/", {}, format="json")
        self.assertEqual(response.status_code, 201)
        payload = self._payload(response)
        return Game.objects.get(id=payload["id"])

    def _set_last_move_at(self, game: Game, value) -> None:
        Game.objects.filter(id=game.id).update(last_move_at=value)
        game.refresh_from_db()

    def _assert_no_highlight_fields(self, payload: dict) -> None:
        for field in self.FRONTEND_ONLY_HIGHLIGHT_FIELDS:
            self.assertNotIn(field, payload)

    def _assert_game_state_payload(self, payload: dict) -> None:
        expected_keys = {
            "id",
            "status",
            "board",
            "turn",
            "winner",
            "timeRemaining",
            "lightTimeRemaining",
            "darkTimeRemaining",
            "moveLog",
        }

        self.assertEqual(set(payload.keys()), expected_keys)
        self._assert_no_highlight_fields(payload)

        self.assertIn(payload["turn"], PLAYER_VALUES)
        self.assertIn(payload["winner"], (None, *PLAYER_VALUES))
        self._assert_timer_ms(payload["timeRemaining"])
        self._assert_timer_ms(payload["lightTimeRemaining"])
        self._assert_timer_ms(payload["darkTimeRemaining"])
        self._assert_board_payload(payload["board"])
        self._assert_move_log_payload(payload["moveLog"])

    def _assert_timer_ms(self, value: object) -> None:
        self.assertIsInstance(value, int)
        self.assertGreaterEqual(value, 0)
        self.assertEqual(value % 1000, 0)

    def _assert_board_payload(self, board: object) -> None:
        self.assertIsInstance(board, list)
        self.assertEqual(len(board), 8)
        for row in board:
            self.assertIsInstance(row, list)
            self.assertEqual(len(row), 8)
            for cell in row:
                if cell is None:
                    continue
                self.assertIsInstance(cell, dict)
                self.assertEqual(set(cell.keys()), {"player", "isKing"})
                self.assertIn(cell["player"], PLAYER_VALUES)
                self.assertIsInstance(cell["isKing"], bool)

    def _assert_move_log_payload(self, move_log: object) -> None:
        self.assertIsInstance(move_log, list)
        for entry in move_log:
            self.assertIsInstance(entry, dict)
            self.assertEqual(set(entry.keys()), {"notation", "from", "to"})
            self.assertIsInstance(entry["notation"], str)
            self.assertEqual(set(entry["from"].keys()), {"row", "col"})
            self.assertEqual(set(entry["to"].keys()), {"row", "col"})

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


class OpenRouterProviderTemperatureTests(TestCase):
    def setUp(self) -> None:
        self.provider = CheckersOpenRouterProvider(
            model_name="openrouter/free",
            adapter=_NoopOpenRouterAdapter(),
        )

    def test_temperature_varies_by_difficulty(self) -> None:
        test_cases = (
            ("easy", 0.7),
            ("medium", 0.4),
            ("hard", 0.1),
            ("  HARD  ", 0.1),
        )

        for difficulty, expected_temperature in test_cases:
            with self.subTest(difficulty=difficulty):
                payload = self.provider._build_payload(self._build_context(difficulty))
                self.assertEqual(payload["temperature"], expected_temperature)

    def test_temperature_defaults_for_unknown_difficulty(self) -> None:
        payload = self.provider._build_payload(self._build_context("legendary"))
        self.assertEqual(payload["temperature"], 0.4)

    def _build_context(self, difficulty: str) -> CheckersAIMoveContext:
        board = Board.empty(8, 8)
        legal_moves = (
            CheckersAIMoveDecision(from_row=2, from_col=1, to_row=3, to_col=0),
        )

        return CheckersAIMoveContext(
            game_id="game-1",
            board=board,
            current_turn=PLAYER_DARK,
            difficulty=difficulty,
            legal_moves=legal_moves,
        )


class OpenRouterProviderValidationTests(TestCase):
    def setUp(self) -> None:
        self.provider = CheckersOpenRouterProvider(
            model_name="openrouter/free",
            adapter=_NoopOpenRouterAdapter(),
        )

    def test_extract_decision_accepts_camel_case_string_numbers(self) -> None:
        raw_response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "fromRow": "2",
                                "fromCol": "1",
                                "toRow": "3",
                                "toCol": "0",
                            }
                        )
                    }
                }
            ]
        }

        decision = self.provider._extract_decision(raw_response)

        self.assertEqual(
            decision,
            CheckersAIMoveDecision(from_row=2, from_col=1, to_row=3, to_col=0),
        )

    def test_extract_decision_accepts_chatty_text_around_json(self) -> None:
        raw_response = {
            "choices": [
                {
                    "message": {
                        "content": (
                            "Sure, here is the move you asked for.\n"
                            "{\"from_row\": 2, \"from_col\": 1, \"to_row\": 3, \"to_col\": 0}\n"
                            "Good luck!"
                        )
                    }
                }
            ]
        }

        decision = self.provider._extract_decision(raw_response)

        self.assertEqual(
            decision,
            CheckersAIMoveDecision(from_row=2, from_col=1, to_row=3, to_col=0),
        )

    def test_extract_decision_raises_on_invalid_shape(self) -> None:
        raw_response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "fromRow": "not-an-int",
                                "fromCol": "1",
                                "toRow": "3",
                                "toCol": "0",
                            }
                        )
                    }
                }
            ]
        }

        with self.assertRaises(CheckersAIProviderInvalidResponseError) as error_context:
            self.provider._extract_decision(raw_response)

        self.assertIn("Move payload validation failed", str(error_context.exception))
