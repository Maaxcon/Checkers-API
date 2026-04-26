from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from checkers.ai.models import (
    CheckersAIProviderError,
    CheckersAIProviderIllegalMoveError,
    CheckersAIProviderInvalidResponseError,
    CheckersAIProviderTimeoutError,
    CheckersAIProviderUnavailableError,
)
from checkers.constants import (
    DEFAULT_PLAYER_TIME_SECONDS,
    GAME_STATUS_FINISHED,
    GAME_STATUS_IN_PROGRESS,
    PLAYER_DARK,
    PLAYER_LIGHT,
    PLAYER_VALUES,
)
from checkers.serializers import GameStateSerializer
from checkers.services.ai_move_service import choose_checkers_ai_move
from checkers.services.constants import MOVE_TYPE_CAPTURE
from checkers.models import Game, MoveEntry
from checkers.services.board import create_initial_board
from checkers.services.converters import SerializedBoard, board_to_json, json_to_board
from checkers.services.logic import apply_move, get_chain_capture_moves, get_legal_moves_for_player, get_opponent, get_winner
from checkers.services.move_entry_utils import (
    extract_checkers_player_from_serialized_board as _extract_player_from_board,
    extract_checkers_position as _extract_pos,
    resolve_checkers_forced_chain_moves as _get_forced_chain_moves,
)
from checkers.services.types import Board, MoveType, Player


@dataclass
class GameServiceError(Exception):
    message: str
    status_code: int = 400
    details: dict[str, object] | None = None

    def to_payload(self) -> dict[str, object]:
        payload = {"error": self.message}
        if self.details:
            payload.update(self.details)
        return payload


def create_game() -> dict[str, object]:
    initial_board = board_to_json(create_initial_board())
    game = Game.objects.create(board=initial_board)
    return _serialize_game(game)


def get_game(game_id: UUID) -> dict[str, object]:
    game = _get_game(game_id)
    _apply_lazy_timeout(game)
    return _serialize_game(game)


def make_move(
    game_id: UUID,
    from_row: int,
    from_col: int,
    to_row: int,
    to_col: int,
    expected_state_version: int | None = None,
    ai_request_id: str | None = None,
) -> dict[str, object]:
    with transaction.atomic():
        game = _get_game_for_update(game_id)
        _ensure_game_in_progress(game)
        if ai_request_id is not None:
            ai_request_id = ai_request_id.strip()
            if not ai_request_id:
                ai_request_id = None

        if ai_request_id and _is_move_request_already_processed(game, ai_request_id):
            return _serialize_game(game)

        if expected_state_version is not None and game.state_version != expected_state_version:
            return _serialize_game(game)

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
            ai_request_id,
        )

    return _serialize_game(game)


def make_ai_move(
    game_id: UUID,
    difficulty: str,
    ai_request_id: str,
) -> dict[str, object]:
    game = _get_game(game_id)
    _apply_lazy_timeout(game)
    _ensure_game_in_progress(game)
    expected_state_version = game.state_version
    resolved_ai_request_id = _resolve_required_ai_request_id(ai_request_id)

    try:
        decision = choose_checkers_ai_move(game=game, difficulty=difficulty)
    except ValueError as error:
        raise _map_ai_configuration_or_validation_error(error) from error
    except CheckersAIProviderTimeoutError as error:
        raise GameServiceError(
            "AI provider timeout",
            status_code=504,
            details={"provider": error.provider},
        ) from error
    except CheckersAIProviderUnavailableError as error:
        raise GameServiceError(
            "AI provider unavailable",
            status_code=503,
            details={"provider": error.provider},
        ) from error
    except CheckersAIProviderInvalidResponseError as error:
        raise GameServiceError(
            "AI provider returned invalid response",
            status_code=502,
            details={"provider": error.provider},
        ) from error
    except CheckersAIProviderIllegalMoveError as error:
        raise GameServiceError(
            "AI provider returned illegal move",
            status_code=502,
            details={"provider": error.provider},
        ) from error
    except CheckersAIProviderError as error:
        raise GameServiceError(
            "AI provider error",
            status_code=502,
            details={"provider": error.provider},
        ) from error

    return make_move(
        game_id=game_id,
        from_row=decision.from_row,
        from_col=decision.from_col,
        to_row=decision.to_row,
        to_col=decision.to_col,
        expected_state_version=expected_state_version,
        ai_request_id=resolved_ai_request_id,
    )


def _consume_move_time_or_fail(game: Game) -> tuple[datetime, int]:
    now = timezone.now()
    time_spent = max(0, int((now - game.last_move_at).total_seconds()))
    current_time_remaining = _get_current_turn_time_remaining(game)

    if time_spent >= current_time_remaining:
        _set_current_turn_time_remaining(game, 0)
        game.status = GAME_STATUS_FINISHED
        game.winner = get_opponent(game.current_turn)
        game.last_move_at = now
        game.save()
        raise GameServiceError(
            "Time is over. Move is not counted.",
            status_code=400,
            details={
                "status": game.status,
                "winner": game.winner,
                "time_remaining": _seconds_to_milliseconds(_get_current_turn_time_remaining(game)),
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
    is_jump = requested_move.type == MOVE_TYPE_CAPTURE
    captured_pos: list[int] | None = None
    switch_turn = True

    if is_jump:
        captured_pos = [requested_move.captured_row, requested_move.captured_col]
        chain_moves = get_chain_capture_moves(new_board, to_row, to_col)
        if chain_moves:
            switch_turn = False

    if switch_turn:
        game.current_turn = get_opponent(game.current_turn)

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


def _save_board_state(game: Game, new_board: Board, now: datetime) -> SerializedBoard:
    board_before = cast(SerializedBoard, game.board)
    game.board = board_to_json(new_board)
    game.last_move_at = now
    game.state_version += 1
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
    board_before: SerializedBoard,
    time_spent: int,
    ai_request_id: str | None,
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
        ai_request_id=ai_request_id,
    )


def undo_move(game_id: UUID) -> dict[str, object]:
    with transaction.atomic():
        game = _get_game_for_update(game_id)
        _apply_lazy_timeout(game)
        _ensure_game_in_progress(game)
        turn_moves, mover_player = _get_last_turn_moves_for_undo(game)

        if not turn_moves:
            raise GameServiceError("No moves to undo")

        oldest_turn_move = turn_moves[-1]
        board_before = cast(SerializedBoard, oldest_turn_move.board_before)
        restored_time_spent = sum(move.time_spent for move in turn_moves)

        game.board = board_before
        if mover_player in PLAYER_VALUES:
            game.current_turn = mover_player
        _add_player_time_remaining(game, game.current_turn, restored_time_spent)
        game.status = GAME_STATUS_IN_PROGRESS
        game.winner = None
        game.last_move_at = timezone.now()
        game.state_version += 1
        game.save()
        game.moves.filter(id__in=[move.id for move in turn_moves]).delete()

    return _serialize_game(game)


def restart_game(game_id: UUID) -> dict[str, object]:
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
        game.state_version += 1
        game.save()

    return _serialize_game(game)


def get_move_history(game_id: UUID) -> dict[str, object]:
    game = _get_game(game_id)
    _apply_lazy_timeout(game)
    moves = list(game.moves.order_by("created_at", "id"))

    return {
        "game_id": str(game.id),
        "move_log": _build_move_log(moves),
    }


def _get_game_for_update(game_id: UUID) -> Game:
    try:
        return Game.objects.select_for_update().get(id=game_id)
    except Game.DoesNotExist as error:
        raise GameServiceError("Game not found", status_code=404) from error


def _get_game(game_id: UUID) -> Game:
    try:
        return Game.objects.get(id=game_id)
    except Game.DoesNotExist as error:
        raise GameServiceError("Game not found", status_code=404) from error


def _ensure_game_in_progress(game: Game) -> None:
    if game.status != GAME_STATUS_IN_PROGRESS:
        raise GameServiceError("Game is already finished", status_code=409)


def _serialize_game(game: Game) -> dict[str, object]:
    serializer = GameStateSerializer(game)
    payload: dict[str, object] = dict(serializer.data)
    moves = list(game.moves.order_by("created_at", "id"))
    payload["move_log"] = _build_move_log(moves)
    return payload


def _apply_lazy_timeout(game: Game) -> None:
    if game.status != GAME_STATUS_IN_PROGRESS:
        return

    now = timezone.now()
    elapsed = max(0, int((now - game.last_move_at).total_seconds()))
    if elapsed == 0:
        return

    time_remaining = max(0, _get_current_turn_time_remaining(game) - elapsed)
    _set_current_turn_time_remaining(game, time_remaining)
    if time_remaining == 0:
        game.status = GAME_STATUS_FINISHED
        game.winner = get_opponent(game.current_turn)

    game.last_move_at = now
    game.save()


def _get_current_turn_time_remaining(game: Game) -> int:
    return _get_player_time_remaining(game, game.current_turn)


def _get_player_time_remaining(game: Game, player: Player) -> int:
    if player == PLAYER_LIGHT:
        return game.light_time_remaining
    if player == PLAYER_DARK:
        return game.dark_time_remaining
    raise GameServiceError(f"Unsupported player value: {player}")


def _set_current_turn_time_remaining(game: Game, value: int) -> None:
    _set_player_time_remaining(game, game.current_turn, value)


def _set_player_time_remaining(game: Game, player: Player, value: int) -> None:
    if player == PLAYER_LIGHT:
        game.light_time_remaining = value
        return
    if player == PLAYER_DARK:
        game.dark_time_remaining = value
        return
    raise GameServiceError(f"Unsupported player value: {player}")


def _add_player_time_remaining(game: Game, player: Player, delta_seconds: int) -> None:
    updated_time = _get_player_time_remaining(game, player) + delta_seconds
    _set_player_time_remaining(game, player, updated_time)


def _is_move_request_already_processed(game: Game, ai_request_id: str) -> bool:
    return MoveEntry.objects.filter(game=game, ai_request_id=ai_request_id).exists()


def _resolve_required_ai_request_id(ai_request_id: str) -> str:
    cleaned = ai_request_id.strip()
    if not cleaned:
        raise GameServiceError("ai_request_id is required", status_code=400)
    return cleaned


def _map_ai_configuration_or_validation_error(error: ValueError) -> GameServiceError:
    message = str(error).strip() or "Unknown AI error"
    if _is_ai_configuration_error_message(message):
        return GameServiceError(
            "AI configuration error",
            status_code=503,
            details={"details": message},
        )
    return GameServiceError(
        "AI validation error",
        status_code=502,
        details={"details": message},
    )


def _is_ai_configuration_error_message(message: str) -> bool:
    config_markers = (
        "OPENROUTER_API_KEY",
        "AI_OPENROUTER_MODELS",
        "AI_TIMEOUT_MS",
        "AI_MAX_RETRIES",
        "model_name",
        "max_retries",
    )
    return any(marker in message for marker in config_markers)


def _get_last_turn_moves_for_undo(game: Game) -> tuple[list[MoveEntry], Player | None]:
    moves_desc = list(game.moves.select_for_update().order_by("-created_at", "-id"))
    if not moves_desc:
        return [], None

    first_move = moves_desc[0]
    mover_player = _extract_player_from_board(
        cast(SerializedBoard, first_move.board_before),
        first_move.from_pos,
    )

    # Fallback to single-step undo when player cannot be determined safely.
    if mover_player not in PLAYER_VALUES:
        return [first_move], mover_player

    turn_moves = [first_move]
    for move in moves_desc[1:]:
        move_player = _extract_player_from_board(
            cast(SerializedBoard, move.board_before),
            move.from_pos,
        )
        if move_player != mover_player:
            break
        turn_moves.append(move)

    return turn_moves, mover_player


def _build_move_log(moves: list[MoveEntry]) -> list[dict[str, object]]:
    move_log: list[dict[str, object]] = []
    last_player: Player | None = None

    for move in moves:
        from_row, from_col = _extract_pos(move.from_pos)
        to_row, to_col = _extract_pos(move.to_pos)
        if from_row is None or from_col is None or to_row is None or to_col is None:
            continue

        mover_player = _extract_player_from_board(cast(SerializedBoard, move.board_before), move.from_pos)
        is_capture = bool(move.is_jump)

        if move_log and mover_player is not None and mover_player == last_player and is_capture:
            last_entry = dict(move_log[-1])
            last_entry["notation"] = _append_capture_notation(cast(str, last_entry["notation"]), to_row, to_col)
            last_entry["to"] = {"row": to_row, "col": to_col}
            move_log[-1] = last_entry
            continue

        move_log.append(
            {
                "notation": _format_move_notation(from_row, from_col, to_row, to_col, is_capture),
                "from": {"row": from_row, "col": from_col},
                "to": {"row": to_row, "col": to_col},
            }
        )
        last_player = mover_player

    return move_log


def _to_notation(row: int, col: int) -> str:
    letters = ("a", "b", "c", "d", "e", "f", "g", "h")
    number = 8 - row
    return f"{letters[col]}{number}"


def _format_move_notation(from_row: int, from_col: int, to_row: int, to_col: int, is_capture: bool) -> str:
    from_notation = _to_notation(from_row, from_col)
    to_notation = _to_notation(to_row, to_col)
    separator = " x " if is_capture else "-"
    return f"{from_notation}{separator}{to_notation}"


def _append_capture_notation(notation: str, to_row: int, to_col: int) -> str:
    return f"{notation}x{_to_notation(to_row, to_col)}"


def _seconds_to_milliseconds(seconds: int) -> int:
    return seconds * 1000
