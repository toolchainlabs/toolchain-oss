# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0019_auto_20210527_1713"),
    ]

    operations = [
        migrations.RenameField(
            model_name="impersonationsession",
            old_name="requested_at",
            new_name="created_at",
        ),
    ]
