# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import shortuuid.main
from django.db import migrations, models

import toolchain.base.datetime_tools
import toolchain.users.models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0017_auto_20210407_2005"),
    ]

    operations = [
        migrations.CreateModel(
            name="ImpersonationSession",
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
                ("user_api_id", models.CharField(editable=False, max_length=22)),
                ("impersonator_api_id", models.CharField(editable=False, max_length=22)),
                ("requested_at", models.DateTimeField(default=toolchain.base.datetime_tools.utcnow, editable=False)),
                (
                    "expires_at",
                    models.DateTimeField(
                        default=toolchain.users.models._default_impersonation_session_expires_at, editable=False
                    ),
                ),
                ("started", models.BooleanField(default=False, editable=False)),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
