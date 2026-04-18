from typing import TypedDict

from .types import Board, Piece, Player


class SerializedPiece(TypedDict):
    player: Player
    is_king: bool


SerializedBoard = list[list[SerializedPiece | None]]


def board_to_json(board: Board) -> SerializedBoard:
    return [
        [({"player": p.player, "is_king": p.is_king} if p else None) for p in row]
        for row in board
    ]


def json_to_board(board_json: SerializedBoard) -> Board:
    return [
        [(Piece(player=p["player"], is_king=p["is_king"]) if p else None) for p in row]
        for row in board_json
    ]
