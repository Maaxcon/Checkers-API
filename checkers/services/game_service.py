from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from checkers.constants import (
    API_STATUS_OK,
    DEFAULT_PLAYER_TIME_SECONDS,
    GAME_STATUS_FINISHED,
    GAME_STATUS_IN_PROGRESS,
    PLAYER_DARK,
    PLAYER_LIGHT,
    PLAYER_VALUES,
)
from checkers.models import Game, MoveEntry
from engine.board import create_initial_board
from engine.logic import apply_move, get_chain_capture_moves, get_legal_moves_for_player, get_winner
from engine.serializers import board_to_json, json_to_board


@dataclass
class GameServiceError(Exception):
    message: str
    status_code: int = 400
    details: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        payload = {"error": self.message}
        if self.details:
            payload.update(self.details)
        return payload


def create_game() -> dict[str, Any]:
    initial_board = board_to_json(create_initial_board())
    game = Game.objects.create(board=initial_board)
    return _serialize_game(game)


def get_game(game_id: UUID) -> dict[str, Any]:
    with transaction.atomic():
        game = _get_game_for_update(game_id)

        displayed_time_remaining = game.player_time_remaining
        if game.status == GAME_STATUS_IN_PROGRESS:
            now = timezone.now()
            elapsed = max(0, int((now - game.last_move_at).total_seconds()))
            displayed_time_remaining = max(0, game.player_time_remaining - elapsed)

            if displayed_time_remaining == 0:
                game.player_time_remaining = 0
                game.status = GAME_STATUS_FINISHED
                game.winner = _opponent(game.current_turn)
                game.last_move_at = now
                game.save()
                displayed_time_remaining = 0

    return _serialize_game(game, time_remaining=displayed_time_remaining)


def make_move(game_id: UUID, from_row: int, from_col: int, to_row: int, to_col: int) -> dict[str, Any]:
    with transaction.atomic():
        game = _get_game_for_update(game_id)
        _ensure_game_in_progress(game)

        now = timezone.now()
        time_spent = max(0, int((now - game.last_move_at).total_seconds()))
        if time_spent >= game.player_time_remaining:
            game.player_time_remaining = 0
            game.status = GAME_STATUS_FINISHED
            game.winner = _opponent(game.current_turn)
            game.last_move_at = now
            game.save()
            raise GameServiceError(
                "Time is over. Move is not counted.",
                status_code=400,
                details={
                    "status": game.status,
                    "winner": game.winner,
                    "time_remaining": game.player_time_remaining,
                },
            )

        game.player_time_remaining -= time_spent

        board = json_to_board(game.board)
        legal_moves = get_legal_moves_for_player(board, game.current_turn)
        requested_move = next(
            (
                move
                for move in legal_moves
                if move.from_row == from_row
                and move.from_col == from_col
                and move.row == to_row
                and move.col == to_col
            ),
            None,
        )

        if requested_move is None:
            raise GameServiceError("Illegal move")

        try:
            new_board = apply_move(board, requested_move)
        except ValueError as error:
            raise GameServiceError(str(error)) from error

        is_jump = requested_move.type == "capture"
        captured_pos = None
        switch_turn = True

        if is_jump:
            captured_pos = [requested_move.captured_row, requested_move.captured_col]
            chain_moves = get_chain_capture_moves(new_board, to_row, to_col)
            if chain_moves:
                switch_turn = False

        if switch_turn:
            game.current_turn = _opponent(game.current_turn)

        winner = get_winner(new_board, game.current_turn)
        if winner:
            game.status = GAME_STATUS_FINISHED
            game.winner = winner

        moved_piece_before = board[from_row][from_col]
        moved_piece_after = new_board[to_row][to_col]
        is_promoted = bool(
            moved_piece_before
            and moved_piece_after
            and not moved_piece_before.is_king
            and moved_piece_after.is_king
        )

        board_before = game.board
        game.board = board_to_json(new_board)
        game.last_move_at = now
        game.save()

        MoveEntry.objects.create(
            game=game,
            from_pos=[from_row, from_col],
            to_pos=[to_row, to_col],
            is_jump=is_jump,
            captured_pos=captured_pos,
            is_promoted=is_promoted,
            board_before=board_before,
            time_spent=time_spent,
        )

    return {
        "status": API_STATUS_OK,
        "board": game.board,
        "turn": game.current_turn,
        "winner": game.winner,
        "time_remaining": game.player_time_remaining,
    }


def undo_move(game_id: UUID) -> dict[str, Any]:
    with transaction.atomic():
        game = _get_game_for_update(game_id)
        last_move = game.moves.select_for_update().order_by("-created_at", "-id").first()

        if last_move is None:
            raise GameServiceError("No moves to undo")

        board_before = last_move.board_before
        from_row, from_col = last_move.from_pos

        mover_player = None
        try:
            piece_data = board_before[from_row][from_col]
            if piece_data:
                mover_player = piece_data.get("player")
        except (IndexError, KeyError, TypeError):
            mover_player = None

        game.board = board_before
        if mover_player in PLAYER_VALUES:
            game.current_turn = mover_player
        game.status = GAME_STATUS_IN_PROGRESS
        game.winner = None
        game.player_time_remaining += last_move.time_spent
        game.last_move_at = timezone.now()
        game.save()
        last_move.delete()

    return {
        "status": API_STATUS_OK,
        "board": game.board,
        "turn": game.current_turn,
        "winner": game.winner,
        "time_remaining": game.player_time_remaining,
    }


def restart_game(game_id: UUID) -> dict[str, Any]:
    with transaction.atomic():
        game = _get_game_for_update(game_id)

        game.moves.all().delete()
        game.board = board_to_json(create_initial_board())
        game.status = GAME_STATUS_IN_PROGRESS
        game.current_turn = PLAYER_LIGHT
        game.winner = None
        game.player_time_remaining = DEFAULT_PLAYER_TIME_SECONDS
        game.last_move_at = timezone.now()
        game.save()

    return {
        "status": API_STATUS_OK,
        "board": game.board,
        "turn": game.current_turn,
        "winner": game.winner,
        "time_remaining": game.player_time_remaining,
    }


def get_move_history(game_id: UUID) -> dict[str, Any]:
    try:
        game = Game.objects.get(id=game_id)
    except Game.DoesNotExist as error:
        raise GameServiceError("Game not found", status_code=404) from error

    moves = game.moves.order_by("created_at", "id")
    return {
        "game_id": str(game.id),
        "moves": [
            {
                "id": move.id,
                "from_pos": move.from_pos,
                "to_pos": move.to_pos,
                "is_jump": move.is_jump,
                "captured_pos": move.captured_pos,
                "is_promoted": move.is_promoted,
                "board_before": move.board_before,
                "time_spent": move.time_spent,
                "created_at": move.created_at.isoformat(),
            }
            for move in moves
        ],
    }


def _get_game_for_update(game_id: UUID) -> Game:
    try:
        return Game.objects.select_for_update().get(id=game_id)
    except Game.DoesNotExist as error:
        raise GameServiceError("Game not found", status_code=404) from error


def _ensure_game_in_progress(game: Game) -> None:
    if game.status != GAME_STATUS_IN_PROGRESS:
        raise GameServiceError("Game is already finished")


def _opponent(player: str) -> str:
    return PLAYER_DARK if player == PLAYER_LIGHT else PLAYER_LIGHT


def _serialize_game(game: Game, time_remaining: int | None = None) -> dict[str, Any]:
    return {
        "id": str(game.id),
        "status": game.status,
        "board": game.board,
        "turn": game.current_turn,
        "winner": game.winner,
        "time_remaining": game.player_time_remaining if time_remaining is None else time_remaining,
    }
