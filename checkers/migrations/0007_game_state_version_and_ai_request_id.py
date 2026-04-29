from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("checkers", "0006_player_values_to_int"),
    ]

    operations = [
        migrations.AddField(
            model_name="game",
            name="state_version",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="moveentry",
            name="ai_request_id",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddConstraint(
            model_name="moveentry",
            constraint=models.UniqueConstraint(
                condition=Q(ai_request_id__isnull=False),
                fields=("game", "ai_request_id"),
                name="uniq_moveentry_game_ai_request_id",
            ),
        ),
    ]
