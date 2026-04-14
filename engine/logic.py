from __future__ import annotations

from typing import Optional

from .board import clone_board, get_piece, is_valid_position
from .constants import BOARD, PLAYERS, TOP_ROW_INDEX
from .moves import get_moves_for_piece
from .types import Board, CaptureMove, Move, MoveType, Piece, Player


def apply_move(board: Board, move: MoveType) -> Board:
    if not is_valid_position(move.from_row, move.from_col):
        raise ValueError("Source position is out of board bounds")
    if not is_valid_position(move.row, move.col):
        raise ValueError("Target position is out of board bounds")

    legal_moves = get_legal_moves_for_piece(board, move.from_row, move.from_col)
    if move not in legal_moves:
        raise ValueError("Move is not legal for the selected piece")

    new_board = clone_board(board)

    piece = new_board[move.from_row][move.from_col]
    assert piece is not None, "Legal move must have a source piece"
    assert new_board[move.row][move.col] is None, "Legal move must target an empty square"

    new_board[move.from_row][move.from_col] = None

    if move.type == "capture":
        captured_piece = new_board[move.captured_row][move.captured_col]
        assert is_valid_position(
            move.captured_row, move.captured_col
        ), "Legal capture must have valid captured coordinates"
        assert captured_piece is not None, "Legal capture must have a captured piece"
        assert captured_piece.player != piece.player, "Legal capture must target an opponent piece"

        new_board[move.captured_row][move.captured_col] = None

    reached_promotion_row = (
        (piece.player == PLAYERS.LIGHT and move.row == TOP_ROW_INDEX)
        or (piece.player == PLAYERS.DARK and move.row == BOARD.ROWS - 1)
    )
    is_king = piece.is_king or reached_promotion_row

    new_board[move.row][move.col] = Piece(player=piece.player, is_king=is_king)
    return new_board


def get_winner(board: Board, turn: Player) -> Optional[Player]:
    if not _player_has_pieces(board, PLAYERS.LIGHT):
        return PLAYERS.DARK
    if not _player_has_pieces(board, PLAYERS.DARK):
        return PLAYERS.LIGHT

    if not get_legal_moves_for_player(board, turn):
        return get_opponent(turn)

    return None


def get_legal_moves_for_player(board: Board, player: Player) -> list[MoveType]:
    player_moves = _get_player_moves(board, player)
    capture_moves = _filter_capture_moves(player_moves)
    if capture_moves:
        return capture_moves
    return player_moves


def get_legal_moves_for_piece(board: Board, row: int, col: int) -> list[MoveType]:
    piece = get_piece(board, row, col)
    if piece is None:
        return []

    piece_moves = get_moves_for_piece(board, row, col)
    if not piece_moves:
        return []

    capture_moves = _filter_capture_moves(piece_moves)
    if capture_moves:
        return capture_moves
    return piece_moves


def get_chain_capture_moves(board: Board, row: int, col: int) -> list[MoveType]:
    piece = get_piece(board, row, col)
    if piece is None:
        return []

    piece_moves = get_moves_for_piece(board, row, col)
    return _filter_capture_moves(piece_moves)


def get_opponent(player: Player) -> Player:
    return PLAYERS.DARK if player == PLAYERS.LIGHT else PLAYERS.LIGHT


def _player_has_pieces(board: Board, player: Player) -> bool:
    for row in board:
        for piece in row:
            if piece is not None and piece.player == player:
                return True
    return False


def _get_player_moves(board: Board, player: Player) -> list[MoveType]:
    moves: list[MoveType] = []
    for row in range(BOARD.ROWS):
        for col in range(BOARD.COLS):
            piece = get_piece(board, row, col)
            if piece is not None and piece.player == player:
                moves.extend(get_moves_for_piece(board, row, col))
    return moves


def _filter_capture_moves(moves: list[MoveType]) -> list[MoveType]:
    return [move for move in moves if move.type == "capture"]
