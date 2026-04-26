import uuid
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .constants import (
    DEFAULT_PLAYER_TIME_SECONDS,
    GAME_STATUS_IN_PROGRESS,
    PLAYER_DARK,
    PLAYER_LIGHT,
)

PLAYER_CHOICES = (
    (PLAYER_LIGHT, "light"),
    (PLAYER_DARK, "dark"),
)


class Game(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    board = models.JSONField()
    status = models.CharField(max_length=20, default=GAME_STATUS_IN_PROGRESS)
    current_turn = models.PositiveSmallIntegerField(choices=PLAYER_CHOICES, default=PLAYER_LIGHT)
    winner = models.PositiveSmallIntegerField(choices=PLAYER_CHOICES, null=True, blank=True)
    light_time_remaining = models.PositiveIntegerField(default=DEFAULT_PLAYER_TIME_SECONDS)
    dark_time_remaining = models.PositiveIntegerField(default=DEFAULT_PLAYER_TIME_SECONDS)
    state_version = models.PositiveIntegerField(default=0)
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
    ai_request_id = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["game", "ai_request_id"],
                condition=Q(ai_request_id__isnull=False),
                name="uniq_moveentry_game_ai_request_id",
            )
        ]

    def __str__(self) -> str:
        return f"Move in {self.game.id}: {self.from_pos} -> {self.to_pos}"
