from rest_framework import serializers

from checkers.constants import PLAYER_DARK, PLAYER_LIGHT
from checkers.models import Game
from checkers.services.constants import BOARD, MIN_INPUT_INDEX


class MoveRequestSerializer(serializers.Serializer):
    from_row = serializers.IntegerField(min_value=MIN_INPUT_INDEX, max_value=BOARD.ROWS - 1)
    from_col = serializers.IntegerField(min_value=MIN_INPUT_INDEX, max_value=BOARD.COLS - 1)
    to_row = serializers.IntegerField(min_value=MIN_INPUT_INDEX, max_value=BOARD.ROWS - 1)
    to_col = serializers.IntegerField(min_value=MIN_INPUT_INDEX, max_value=BOARD.COLS - 1)


class GameStateSerializer(serializers.ModelSerializer):
    turn = serializers.CharField(source="current_turn", read_only=True)
    status = serializers.SerializerMethodField()
    time_remaining = serializers.SerializerMethodField()
    light_time_remaining = serializers.SerializerMethodField()
    dark_time_remaining = serializers.SerializerMethodField()

    class Meta:
        model = Game
        fields = (
            "id",
            "status",
            "board",
            "turn",
            "winner",
            "time_remaining",
            "light_time_remaining",
            "dark_time_remaining",
        )
        read_only_fields = fields

    def get_status(self, obj: Game) -> str:
        status_override = self.context.get("status_override")
        if status_override is not None:
            return status_override
        return obj.status

    def get_time_remaining(self, obj: Game) -> int:
        time_remaining_override = self.context.get("time_remaining_override")
        if time_remaining_override is not None:
            return time_remaining_override
        return self._get_current_turn_time(obj)

    def get_light_time_remaining(self, obj: Game) -> int:
        time_remaining_override = self.context.get("time_remaining_override")
        if time_remaining_override is not None and obj.current_turn == PLAYER_LIGHT:
            return time_remaining_override
        return obj.light_time_remaining

    def get_dark_time_remaining(self, obj: Game) -> int:
        time_remaining_override = self.context.get("time_remaining_override")
        if time_remaining_override is not None and obj.current_turn == PLAYER_DARK:
            return time_remaining_override
        return obj.dark_time_remaining

    def _get_current_turn_time(self, obj: Game) -> int:
        if obj.current_turn == PLAYER_LIGHT:
            return obj.light_time_remaining
        return obj.dark_time_remaining
