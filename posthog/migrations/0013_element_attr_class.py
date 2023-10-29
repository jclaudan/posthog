# Generated by Django 2.2.7 on 2020-01-29 05:32

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("posthog", "0012_team_app_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="element",
            name="attr_class",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(blank=True, max_length=200),
                blank=True,
                null=True,
                size=None,
            ),
        ),
    ]
