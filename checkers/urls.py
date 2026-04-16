from django.urls import path
from . import views

urlpatterns = [
    # POST /api/games/
    path('games/', views.create_game, name='create_game'),
    
    # GET /api/games/{id}/
    path('games/<uuid:game_id>/', views.get_game, name='get_game'),
    
    # POST /api/games/{id}/move/
    path('games/<uuid:game_id>/move/', views.make_move, name='make_move'),
    
    # POST /api/games/{id}/undo/
    path('games/<uuid:game_id>/undo/', views.undo_move, name='undo_move'),
    
    # POST /api/games/{id}/restart/
    path('games/<uuid:game_id>/restart/', views.restart_game, name='restart_game'),
    
    # GET /api/games/{id}/moves/
    path('games/<uuid:game_id>/moves/', views.get_move_history, name='get_move_history'),
]