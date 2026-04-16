from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from .models import Game
from engine.board import create_initial_board
from engine.serializers import board_to_json

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
