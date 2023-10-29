# Generated by Django 3.0.7 on 2020-09-24 00:23

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import posthog.models.utils


class Migration(migrations.Migration):
    dependencies = [
        ("posthog", "0089_auto_20201015_1031"),
    ]

    operations = [
        migrations.AlterField(
            model_name="personalapikey",
            name="team",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="personal_api_keys+",
                to="posthog.Team",
            ),
        ),
        migrations.AlterField(
            model_name="team",
            name="api_token",
            field=models.CharField(
                default=posthog.models.utils.generate_random_token,
                max_length=200,
                null=True,
                unique=True,
            ),
        ),
        migrations.AlterField(
            model_name="team",
            name="users",
            field=models.ManyToManyField(
                blank=True,
                related_name="teams_deprecated_relationship",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="person",
            name="uuid",
            field=models.UUIDField(db_index=True, default=posthog.models.utils.UUIDT, editable=False),
        ),
        migrations.AlterField(
            model_name="team",
            name="name",
            field=models.CharField(default="Default Project", max_length=200, null=True),
        ),
        migrations.RemoveConstraint(
            model_name="organizationinvite",
            name="max_uses_respected",
        ),
        migrations.RemoveField(
            model_name="organizationinvite",
            name="last_used_by",
        ),
        migrations.RemoveField(
            model_name="organizationinvite",
            name="max_uses",
        ),
        migrations.RemoveField(
            model_name="organizationinvite",
            name="uses",
        ),
        migrations.AlterField(
            model_name="organizationinvite",
            name="target_email",
            field=models.EmailField(db_index=True, max_length=254, null=True),
        ),
    ]
