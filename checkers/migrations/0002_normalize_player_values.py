from django.db import migrations, models


def normalize_player_values_forward(apps, schema_editor):
    Game = apps.get_model("checkers", "Game")
    Game.objects.filter(current_turn="LIGHT").update(current_turn="light")
    Game.objects.filter(current_turn="DARK").update(current_turn="dark")
    Game.objects.filter(winner="LIGHT").update(winner="light")
    Game.objects.filter(winner="DARK").update(winner="dark")


def normalize_player_values_reverse(apps, schema_editor):
    Game = apps.get_model("checkers", "Game")
    Game.objects.filter(current_turn="light").update(current_turn="LIGHT")
    Game.objects.filter(current_turn="dark").update(current_turn="DARK")
    Game.objects.filter(winner="light").update(winner="LIGHT")
    Game.objects.filter(winner="dark").update(winner="DARK")


class Migration(migrations.Migration):

    dependencies = [
        ("checkers", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            normalize_player_values_forward,
            normalize_player_values_reverse,
        ),
        migrations.AlterField(
            model_name="game",
            name="current_turn",
            field=models.CharField(
                choices=[("light", "light"), ("dark", "dark")],
                default="light",
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="game",
            name="winner",
            field=models.CharField(
                blank=True,
                choices=[("light", "light"), ("dark", "dark")],
                max_length=10,
                null=True,
            ),
        ),
    ]
