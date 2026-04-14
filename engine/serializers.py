from .types import Piece, Board

def board_to_json(board: Board):
    return [
        [(p.__dict__ if p else None) for p in row]
        for row in board
    ]