from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("checkers", "0007_game_state_version_and_ai_request_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="game",
            name="ai_move_pending",
            field=models.BooleanField(default=False),
        ),
    ]
