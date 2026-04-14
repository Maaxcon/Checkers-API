import uuid
from django.db import models

class Game(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    board = models.JSONField()
    status = models.CharField(max_length=20, default='IN_PROGRESS') 
    current_turn = models.CharField(max_length=10, default='LIGHT') 
    winner = models.CharField(max_length=10, null=True, blank=True)
    player_time_remaining = models.IntegerField(default=300) 
    last_move_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Game {self.id} - {self.status}"


class MoveEntry(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='moves')
    from_pos = models.JSONField() 
    to_pos = models.JSONField()
    is_jump = models.BooleanField(default=False)
    captured_pos = models.JSONField(null=True, blank=True)
    is_promoted = models.BooleanField(default=False)
    board_before = models.JSONField()
    time_spent = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Move in {self.game.id}: {self.from_pos} -> {self.to_pos}"