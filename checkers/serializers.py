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
    turn = serializers.IntegerField(source="current_turn", read_only=True)
    status = serializers.CharField(read_only=True)
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

    def get_time_remaining(self, obj: Game) -> int:
        return self._to_milliseconds(self._get_current_turn_time(obj))

    def get_light_time_remaining(self, obj: Game) -> int:
        return self._to_milliseconds(obj.light_time_remaining)

    def get_dark_time_remaining(self, obj: Game) -> int:
        return self._to_milliseconds(obj.dark_time_remaining)

    def _get_current_turn_time(self, obj: Game) -> int:
        if obj.current_turn == PLAYER_LIGHT:
            return obj.light_time_remaining
        return obj.dark_time_remaining

    def _to_milliseconds(self, seconds: int) -> int:
        return seconds * 1000
