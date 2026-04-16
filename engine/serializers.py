from .types import Piece, Board

def board_to_json(board: Board):
    return [
        [(p.__dict__ if p else None) for p in row]
        for row in board
    ]

def json_to_board(board_json: list) -> Board:
    return [
        [(Piece(**p) if p else None) for p in row]
        for row in board_json
    ]