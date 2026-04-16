from rest_framework import serializers


class MoveRequestSerializer(serializers.Serializer):
    from_row = serializers.IntegerField(min_value=0, max_value=7)
    from_col = serializers.IntegerField(min_value=0, max_value=7)
    to_row = serializers.IntegerField(min_value=0, max_value=7)
    to_col = serializers.IntegerField(min_value=0, max_value=7)
