# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import shortuuid.main
from django.db import migrations, models

import toolchain.base.datetime_tools


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0018_auto_20210526_2311"),
    ]

    operations = [
        migrations.CreateModel(
            name="ImpersonationAuditLog",
            fields=[
                (
                    "id",
                    models.CharField(
                        default=shortuuid.main.ShortUUID.uuid,
                        editable=False,
                        max_length=22,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(default=toolchain.base.datetime_tools.utcnow, editable=False)),
                ("session_id", models.CharField(editable=False, max_length=22)),
                ("path", models.CharField(editable=False, max_length=1024)),
                ("method", models.CharField(editable=False, max_length=10)),
                ("data", models.JSONField(default=dict, editable=False)),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
