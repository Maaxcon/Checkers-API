from __future__ import annotations

from typing import Optional

from .board import create_initial_board
from .constants import BOARD, COORD_PARTS_COUNT, MIN_INPUT_INDEX, PLAYERS
from .logic import (
    apply_move,
    get_chain_capture_moves,
    get_legal_moves_for_piece,
    get_opponent,
    get_winner,
)
from .types import Board, MoveType, Piece, Player

def piece_to_char(piece: Piece | None) -> str:
    if piece is None:
        return "."
    if piece.player == "light":
        return "W" if piece.is_king else "w"
    return "B" if piece.is_king else "b"

def print_board(board: Board) -> None:
    print("   " + " ".join(str(col) for col in range(BOARD.COLS)))
    for row_index, row in enumerate(board):
        row_str = " ".join(piece_to_char(cell) for cell in row)
        print(f"{row_index}  {row_str}")

def run_game_loop() -> None:
    board = create_initial_board()
    turn: Player = PLAYERS.LIGHT

    while True:
        print()
        print_board(board)

        winner = get_winner(board, turn)
        if winner is not None:
            print()
            print(f"Winner: {winner}")
            return

        print()
        print(f"Turn: {turn}")
        print("Choose a piece (row col). Type 'q' to quit.")

        selection = _read_piece_selection(board, turn)
        if selection is None:
            print("Game stopped.")
            return

        piece_row, piece_col = selection
        piece_moves = get_legal_moves_for_piece(board, piece_row, piece_col)
        selected_move = _read_move_selection(piece_moves)
        if selected_move is None:
            print("Game stopped.")
            return

        board = apply_move(board, selected_move)
        board, selected_move = _handle_chain_captures(board, selected_move)
        if selected_move is None:
            print("Game stopped.")
            return

        turn = get_opponent(turn)

def _handle_chain_captures(board: Board, last_move: MoveType) -> tuple[Board, Optional[MoveType]]:
    while last_move.type == "capture":
        chain_moves = get_chain_capture_moves(board, last_move.row, last_move.col)
        if not chain_moves:
            break

        print()
        print_board(board)
        print()
        print(f"Chain capture is required from ({last_move.row}, {last_move.col}).")

        next_move = _read_move_selection(chain_moves)
        if next_move is None:
            return board, None

        last_move = next_move
        board = apply_move(board, last_move)

    return board, last_move

def _read_piece_selection(board: Board, turn: Player) -> Optional[tuple[int, int]]:
    while True:
        coords = _read_coords("Piece: ")
        if coords is None:
            return None

        row, col = coords
        piece = board[row][col]
        if piece is None:
            print("No piece at that square.")
            continue
        if piece.player != turn:
            print("That is not your piece.")
            continue

        legal_moves = get_legal_moves_for_piece(board, row, col)
        if not legal_moves:
            print("That piece has no legal moves.")
            continue

        return row, col

def _read_move_selection(moves: list[MoveType]) -> Optional[MoveType]:
    _print_moves(moves)

    while True:
        try:
            raw = input("Move index: ").strip().lower()
        except EOFError:
            return None

        if raw in {"q", "quit", "exit"}:
            return None

        try:
            move_index = int(raw)
        except ValueError:
            print("Enter a number (for example: 0).")
            continue

        if move_index < MIN_INPUT_INDEX or move_index >= len(moves):
            print(f"Choose a value from {MIN_INPUT_INDEX} to {len(moves) - 1}.")
            continue

        return moves[move_index]

def _print_moves(moves: list[MoveType]) -> None:
    print("Available moves:")
    for index, move in enumerate(moves):
        print(f"  [{index}] {_format_move(move)}")

def _format_move(move: MoveType) -> str:
    base = f"({move.from_row}, {move.from_col}) -> ({move.row}, {move.col})"
    if move.type == "capture":
        return (
            f"{base} capture ({move.captured_row}, {move.captured_col})"
        )
    return base

def _read_coords(prompt: str) -> Optional[tuple[int, int]]:
    while True:
        try:
            raw = input(prompt).strip().lower()
        except EOFError:
            return None

        if raw in {"q", "quit", "exit"}:
            return None

        parts = raw.replace(",", " ").split()
        if len(parts) != COORD_PARTS_COUNT:
            print("Enter two numbers: row col")
            continue

        try:
            row = int(parts[0])
            col = int(parts[1])
        except ValueError:
            print("Enter valid integers, for example: 2 3")
            continue

        if (
            row < MIN_INPUT_INDEX
            or row >= BOARD.ROWS
            or col < MIN_INPUT_INDEX
            or col >= BOARD.COLS
        ):
            print(
                f"Coordinates must be in range: row {MIN_INPUT_INDEX}-{BOARD.ROWS - 1}, "
                f"col {MIN_INPUT_INDEX}-{BOARD.COLS - 1}"
            )
            continue

        return row, col

if __name__ == "__main__":
    run_game_loop()