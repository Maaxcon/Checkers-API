from __future__ import annotations

from datetime import datetime
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
from checkers.services.board import create_initial_board
from checkers.services.logic import apply_move, get_chain_capture_moves, get_legal_moves_for_player, get_winner
from checkers.services.converters import board_to_json, json_to_board
from checkers.services.types import Board, MoveType


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
        displayed_time_remaining = _apply_lazy_timeout(game)

    return _serialize_game(game, time_remaining=displayed_time_remaining)


def make_move(game_id: UUID, from_row: int, from_col: int, to_row: int, to_col: int) -> dict[str, Any]:
    with transaction.atomic():
        game = _get_game_for_update(game_id)
        _apply_lazy_timeout(game)
        _ensure_game_in_progress(game)

        now, time_spent = _consume_move_time_or_fail(game)
        board = json_to_board(game.board)
        requested_move = _resolve_requested_move(game, board, from_row, from_col, to_row, to_col)
        new_board = _apply_requested_move(board, requested_move)
        is_jump, captured_pos = _apply_chain_capture_rules(game, new_board, requested_move, to_row, to_col)
        _update_game_winner(game, new_board)

        is_promoted = _is_promotion_move(board, new_board, from_row, from_col, to_row, to_col)
        board_before = _save_board_state(game, new_board, now)
        _create_move_entry(
            game,
            from_row,
            from_col,
            to_row,
            to_col,
            is_jump,
            captured_pos,
            is_promoted,
            board_before,
            time_spent,
        )

    return _serialize_move_result(game)


def _consume_move_time_or_fail(game: Game) -> tuple[datetime, int]:
    now = timezone.now()
    time_spent = max(0, int((now - game.last_move_at).total_seconds()))
    current_time_remaining = _get_current_turn_time_remaining(game)

    if time_spent >= current_time_remaining:
        _set_current_turn_time_remaining(game, 0)
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
                "time_remaining": _get_current_turn_time_remaining(game),
            },
        )

    _set_current_turn_time_remaining(game, current_time_remaining - time_spent)
    return now, time_spent


def _resolve_requested_move(
    game: Game,
    board: Board,
    from_row: int,
    from_col: int,
    to_row: int,
    to_col: int,
) -> MoveType:
    forced_chain_moves = _get_forced_chain_moves(game, board)
    legal_moves = get_legal_moves_for_player(board, game.current_turn)
    if forced_chain_moves is not None:
        legal_moves = forced_chain_moves

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
        if forced_chain_moves is not None:
            raise GameServiceError("You must continue capture with the same piece")
        raise GameServiceError("Illegal move")

    return requested_move


def _apply_requested_move(board: Board, requested_move: MoveType) -> Board:
    try:
        return apply_move(board, requested_move)
    except ValueError as error:
        raise GameServiceError(str(error)) from error


def _apply_chain_capture_rules(
    game: Game,
    new_board: Board,
    requested_move: MoveType,
    to_row: int,
    to_col: int,
) -> tuple[bool, list[int] | None]:
    is_jump = requested_move.type == "capture"
    captured_pos: list[int] | None = None
    switch_turn = True

    if is_jump:
        captured_pos = [requested_move.captured_row, requested_move.captured_col]
        chain_moves = get_chain_capture_moves(new_board, to_row, to_col)
        if chain_moves:
            switch_turn = False

    if switch_turn:
        game.current_turn = _opponent(game.current_turn)

    return is_jump, captured_pos


def _update_game_winner(game: Game, board: Board) -> None:
    winner = get_winner(board, game.current_turn)
    if winner:
        game.status = GAME_STATUS_FINISHED
        game.winner = winner


def _is_promotion_move(
    board_before_move: Board,
    board_after_move: Board,
    from_row: int,
    from_col: int,
    to_row: int,
    to_col: int,
) -> bool:
    moved_piece_before = board_before_move[from_row][from_col]
    moved_piece_after = board_after_move[to_row][to_col]
    return bool(
        moved_piece_before
        and moved_piece_after
        and not moved_piece_before.is_king
        and moved_piece_after.is_king
    )


def _save_board_state(game: Game, new_board: Board, now: datetime) -> Any:
    board_before = game.board
    game.board = board_to_json(new_board)
    game.last_move_at = now
    game.save()
    return board_before


def _create_move_entry(
    game: Game,
    from_row: int,
    from_col: int,
    to_row: int,
    to_col: int,
    is_jump: bool,
    captured_pos: list[int] | None,
    is_promoted: bool,
    board_before: Any,
    time_spent: int,
) -> None:
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


def _serialize_move_result(game: Game) -> dict[str, Any]:
    return {
        "status": API_STATUS_OK,
        "board": game.board,
        "turn": game.current_turn,
        "winner": game.winner,
        "time_remaining": _get_current_turn_time_remaining(game),
        "light_time_remaining": game.light_time_remaining,
        "dark_time_remaining": game.dark_time_remaining,
    }


def undo_move(game_id: UUID) -> dict[str, Any]:
    with transaction.atomic():
        game = _get_game_for_update(game_id)
        _apply_lazy_timeout(game)
        _ensure_game_in_progress(game)
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
        _add_player_time_remaining(game, game.current_turn, last_move.time_spent)
        game.status = GAME_STATUS_IN_PROGRESS
        game.winner = None
        game.last_move_at = timezone.now()
        game.save()
        last_move.delete()

    return {
        "status": API_STATUS_OK,
        "board": game.board,
        "turn": game.current_turn,
        "winner": game.winner,
        "time_remaining": _get_current_turn_time_remaining(game),
        "light_time_remaining": game.light_time_remaining,
        "dark_time_remaining": game.dark_time_remaining,
    }


def restart_game(game_id: UUID) -> dict[str, Any]:
    with transaction.atomic():
        game = _get_game_for_update(game_id)
        _apply_lazy_timeout(game)

        game.moves.all().delete()
        game.board = board_to_json(create_initial_board())
        game.status = GAME_STATUS_IN_PROGRESS
        game.current_turn = PLAYER_LIGHT
        game.winner = None
        game.light_time_remaining = DEFAULT_PLAYER_TIME_SECONDS
        game.dark_time_remaining = DEFAULT_PLAYER_TIME_SECONDS
        game.last_move_at = timezone.now()
        game.save()

    return {
        "status": API_STATUS_OK,
        "board": game.board,
        "turn": game.current_turn,
        "winner": game.winner,
        "time_remaining": _get_current_turn_time_remaining(game),
        "light_time_remaining": game.light_time_remaining,
        "dark_time_remaining": game.dark_time_remaining,
    }


def get_move_history(game_id: UUID) -> dict[str, Any]:
    with transaction.atomic():
        game = _get_game_for_update(game_id)
        _apply_lazy_timeout(game)
        moves = list(game.moves.order_by("created_at", "id"))

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
    light_time_remaining = game.light_time_remaining
    dark_time_remaining = game.dark_time_remaining
    if time_remaining is not None:
        if game.current_turn == PLAYER_LIGHT:
            light_time_remaining = time_remaining
        elif game.current_turn == PLAYER_DARK:
            dark_time_remaining = time_remaining

    return {
        "id": str(game.id),
        "status": game.status,
        "board": game.board,
        "turn": game.current_turn,
        "winner": game.winner,
        "time_remaining": _get_current_turn_time_remaining(game) if time_remaining is None else time_remaining,
        "light_time_remaining": light_time_remaining,
        "dark_time_remaining": dark_time_remaining,
    }


def _apply_lazy_timeout(game: Game) -> int:
    if game.status != GAME_STATUS_IN_PROGRESS:
        return _get_current_turn_time_remaining(game)

    now = timezone.now()
    elapsed = max(0, int((now - game.last_move_at).total_seconds()))
    time_remaining = max(0, _get_current_turn_time_remaining(game) - elapsed)
    if time_remaining == 0:
        _set_current_turn_time_remaining(game, 0)
        game.status = GAME_STATUS_FINISHED
        game.winner = _opponent(game.current_turn)
        game.last_move_at = now
        game.save()

    return time_remaining


def _get_current_turn_time_remaining(game: Game) -> int:
    return _get_player_time_remaining(game, game.current_turn)


def _get_player_time_remaining(game: Game, player: str) -> int:
    if player == PLAYER_LIGHT:
        return game.light_time_remaining
    if player == PLAYER_DARK:
        return game.dark_time_remaining
    raise GameServiceError(f"Unsupported player value: {player}")


def _set_current_turn_time_remaining(game: Game, value: int) -> None:
    _set_player_time_remaining(game, game.current_turn, value)


def _set_player_time_remaining(game: Game, player: str, value: int) -> None:
    if player == PLAYER_LIGHT:
        game.light_time_remaining = value
        return
    if player == PLAYER_DARK:
        game.dark_time_remaining = value
        return
    raise GameServiceError(f"Unsupported player value: {player}")


def _add_player_time_remaining(game: Game, player: str, delta_seconds: int) -> None:
    updated_time = _get_player_time_remaining(game, player) + delta_seconds
    _set_player_time_remaining(game, player, updated_time)


def _get_forced_chain_moves(game: Game, board: Board) -> list[MoveType] | None:
    last_move = game.moves.order_by("-created_at", "-id").first()
    if last_move is None or not last_move.is_jump:
        return None

    mover_player = _extract_player_from_board(last_move.board_before, last_move.from_pos)
    if mover_player != game.current_turn:
        return None

    to_row, to_col = _extract_pos(last_move.to_pos)
    if to_row is None or to_col is None:
        return None

    chain_moves = get_chain_capture_moves(board, to_row, to_col)
    return chain_moves or None


def _extract_player_from_board(board_json: Any, pos: Any) -> str | None:
    row, col = _extract_pos(pos)
    if row is None or col is None:
        return None

    try:
        piece = board_json[row][col]
    except (IndexError, KeyError, TypeError):
        return None

    if isinstance(piece, dict):
        player = piece.get("player")
        if player in PLAYER_VALUES:
            return player
    return None


def _extract_pos(pos: Any) -> tuple[int | None, int | None]:
    if not isinstance(pos, (list, tuple)) or len(pos) != 2:
        return None, None
    if not isinstance(pos[0], int) or not isinstance(pos[1], int):
        return None, None
    return pos[0], pos[1]
