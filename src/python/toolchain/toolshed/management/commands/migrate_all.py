# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from django.conf import settings
from django.core.management.commands.migrate import Command as MigrateDBCommand

from toolchain.base.toolchain_error import ToolchainAssertion


class Command(MigrateDBCommand):
    help = "Migrate all databases"

    def handle(self, *args, **options):
        databases = sorted(settings.DATABASES.keys())
        if len(databases) < 3:
            raise ToolchainAssertion(f"Django DATABASES setting not configured properly: {databases}")
        for db_name in databases:
            if db_name == "default":
                continue
            db_options = dict(options)
            db_options["database"] = db_name
            self.stdout.write(self.style.MIGRATE_HEADING(f"Migrating DB: {db_name}"))
            super().handle(*args, **db_options)
