# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.core.management.base import BaseCommand

from toolchain.users.models import PeriodicallyExportRemoteWorkerTokens


class Command(BaseCommand):
    help = "Configures remote token worker export."

    def handle(self, *args, **options) -> None:
        interval = options["interval_seconds"]
        PeriodicallyExportRemoteWorkerTokens.create_or_update(period_seconds=interval)

    def add_arguments(self, parser):
        parser.add_argument(
            "--interval-seconds",
            type=int,
            required=False,
            default=600,
            help="Export interval (seconds)",
        )
