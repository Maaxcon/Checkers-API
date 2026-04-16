from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from .models import Game, MoveEntry
from engine.board import create_initial_board
from engine.logic import apply_move, get_chain_capture_moves, get_legal_moves_for_player, get_winner
from engine.serializers import board_to_json, json_to_board

@api_view(['POST'])
def create_game(request):
    initial_board = board_to_json(create_initial_board())
    game = Game.objects.create(board=initial_board)

    return Response({
        'id': str(game.id),
        'status': game.status,
        'board': game.board,
        'turn': game.current_turn,
        'winner': game.winner,
        'time_remaining': game.player_time_remaining,
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def get_game(request, game_id):
    game = get_object_or_404(Game, id=game_id)

    return Response({
        'id': str(game.id),
        'status': game.status,
        'board': game.board,
        'turn': game.current_turn,
        'winner': game.winner,
        'time_remaining': game.player_time_remaining,
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
def make_move(request, game_id):
    data = request.data or {}
    try:
        from_row = int(data.get('from_row'))
        from_col = int(data.get('from_col'))
        to_row = int(data.get('to_row'))
        to_col = int(data.get('to_col'))
    except (TypeError, ValueError):
        return Response(
            {'error': 'from_row, from_col, to_row, to_col must be integers'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        game = get_object_or_404(Game.objects.select_for_update(), id=game_id)

        if game.status != 'IN_PROGRESS':
            return Response(
                {'error': 'Game is already finished'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        board = json_to_board(game.board)
        legal_moves = get_legal_moves_for_player(board, game.current_turn)
        requested_move = next(
            (
                move for move in legal_moves
                if move.from_row == from_row
                and move.from_col == from_col
                and move.row == to_row
                and move.col == to_col
            ),
            None,
        )

        if requested_move is None:
            return Response({'error': 'Illegal move'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            new_board = apply_move(board, requested_move)
        except ValueError as error:
            return Response({'error': str(error)}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        time_spent = max(0, int((now - game.last_move_at).total_seconds()))
        game.player_time_remaining = max(0, game.player_time_remaining - time_spent)

        is_jump = requested_move.type == "capture"
        captured_pos = None
        switch_turn = True

        if is_jump:
            captured_pos = [requested_move.captured_row, requested_move.captured_col]
            chain_moves = get_chain_capture_moves(new_board, to_row, to_col)
            if chain_moves:
                switch_turn = False

        if switch_turn:
            game.current_turn = 'dark' if game.current_turn == 'light' else 'light'

        winner = get_winner(new_board, game.current_turn)
        if winner:
            game.status = 'FINISHED'
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

    return Response({
        'status': 'ok',
        'board': game.board,
        'turn': game.current_turn,
        'winner': game.winner,
        'time_remaining': game.player_time_remaining,
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
def undo_move(request, game_id):
    with transaction.atomic():
        game = get_object_or_404(Game.objects.select_for_update(), id=game_id)
        last_move = game.moves.select_for_update().order_by('-created_at', '-id').first()

        if last_move is None:
            return Response({'error': 'No moves to undo'}, status=status.HTTP_400_BAD_REQUEST)

        board_before = last_move.board_before
        from_row, from_col = last_move.from_pos
        mover_player = None
        try:
            piece_data = board_before[from_row][from_col]
            if piece_data:
                mover_player = piece_data.get('player')
        except (IndexError, TypeError, KeyError):
            mover_player = None

        game.board = board_before
        game.current_turn = mover_player if mover_player in ('light', 'dark') else game.current_turn
        game.status = 'IN_PROGRESS'
        game.winner = None
        game.player_time_remaining += last_move.time_spent
        game.last_move_at = timezone.now()
        game.save()

        last_move.delete()

    return Response({
        'status': 'ok',
        'board': game.board,
        'turn': game.current_turn,
        'winner': game.winner,
        'time_remaining': game.player_time_remaining,
    }, status=status.HTTP_200_OK)
