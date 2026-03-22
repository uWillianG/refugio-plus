from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('booking', '0005_alter_schedules_user_name_alter_schedules_user_phone'),
    ]

    operations = [
        migrations.AddField(
            model_name='court_blocks',
            name='fixed_weekday',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='court_blocks',
            name='is_fixed',
            field=models.BooleanField(default=False),
        ),
    ]
