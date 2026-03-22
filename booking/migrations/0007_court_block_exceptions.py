from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0006_court_blocks_fixed_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="court_block_exceptions",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("skip_date", models.DateField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "block_id",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="exceptions",
                        to="booking.court_blocks",
                    ),
                ),
            ],
            options={
                "unique_together": {("block_id", "skip_date")},
            },
        ),
    ]
