import uuid
from django.db import models
from django.utils import timezone

from .constants import (
    DEFAULT_PLAYER_TIME_SECONDS,
    GAME_STATUS_IN_PROGRESS,
    PLAYER_DARK,
    PLAYER_LIGHT,
)

PLAYER_CHOICES = (
    (PLAYER_LIGHT, PLAYER_LIGHT),
    (PLAYER_DARK, PLAYER_DARK),
)


class Game(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    board = models.JSONField()
    status = models.CharField(max_length=20, default=GAME_STATUS_IN_PROGRESS)
    current_turn = models.CharField(max_length=10, choices=PLAYER_CHOICES, default=PLAYER_LIGHT)
    winner = models.CharField(max_length=10, choices=PLAYER_CHOICES, null=True, blank=True)
    light_time_remaining = models.PositiveIntegerField(default=DEFAULT_PLAYER_TIME_SECONDS)
    dark_time_remaining = models.PositiveIntegerField(default=DEFAULT_PLAYER_TIME_SECONDS)
    last_move_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Game {self.id} - {self.status}"


class MoveEntry(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='moves')
    from_pos = models.JSONField() 
    to_pos = models.JSONField()
    is_jump = models.BooleanField(default=False)
    captured_pos = models.JSONField(null=True, blank=True)
    is_promoted = models.BooleanField(default=False)
    board_before = models.JSONField()
    time_spent = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Move in {self.game.id}: {self.from_pos} -> {self.to_pos}"
