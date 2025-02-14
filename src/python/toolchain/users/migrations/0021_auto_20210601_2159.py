# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import shortuuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0020_auto_20210601_1514"),
    ]

    operations = [
        migrations.DeleteModel(
            name="UserAccessConfig",
        ),
        migrations.AlterField(
            model_name="impersonationauditlog",
            name="id",
            field=models.CharField(
                default=shortuuid.uuid, editable=False, max_length=22, primary_key=True, serialize=False
            ),
        ),
        migrations.AlterField(
            model_name="impersonationsession",
            name="id",
            field=models.CharField(
                default=shortuuid.uuid, editable=False, max_length=22, primary_key=True, serialize=False
            ),
        ),
    ]
