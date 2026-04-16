from rest_framework import serializers

from engine.constants import BOARD, MIN_INPUT_INDEX


class MoveRequestSerializer(serializers.Serializer):
    from_row = serializers.IntegerField(min_value=MIN_INPUT_INDEX, max_value=BOARD.ROWS - 1)
    from_col = serializers.IntegerField(min_value=MIN_INPUT_INDEX, max_value=BOARD.COLS - 1)
    to_row = serializers.IntegerField(min_value=MIN_INPUT_INDEX, max_value=BOARD.ROWS - 1)
    to_col = serializers.IntegerField(min_value=MIN_INPUT_INDEX, max_value=BOARD.COLS - 1)
