from typing import Any

from .types import Piece, Board

SerializedPiece = dict[str, Any]
SerializedBoard = list[list[SerializedPiece | None]]

def board_to_json(board: Board) -> SerializedBoard:
    return [
        [(p.__dict__ if p else None) for p in row]
        for row in board
    ]

def json_to_board(board_json: SerializedBoard) -> Board:
    return [
        [(Piece(**p) if p else None) for p in row]
        for row in board_json
    ]
