from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("checkers", "0008_game_ai_move_pending"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="game",
            name="ai_move_pending",
        ),
        migrations.AddField(
            model_name="game",
            name="current_ai_job_id",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
