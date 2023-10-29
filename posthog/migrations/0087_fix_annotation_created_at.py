# Generated by Django 3.0.7 on 2020-10-14 07:46

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("posthog", "0086_team_session_recording_opt_in"),
    ]

    operations = [
        migrations.AlterField(
            model_name="annotation",
            name="created_at",
            field=models.DateTimeField(default=django.utils.timezone.now, null=True),
        ),
    ]
