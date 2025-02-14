# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.core.management.base import BaseCommand

from toolchain.oss_metrics.bugout_integration.models import ScheduleBugoutDataDownload


class Command(BaseCommand):
    help = "Configures bugout data dowload scheduler."

    def handle(self, *args, **options) -> None:
        interval = options["interval_minutes"]
        journal_id = options["journal_id"]
        ScheduleBugoutDataDownload.update_or_create(period_minutes=interval, journal_id=journal_id)

    def add_arguments(self, parser):
        parser.add_argument("--journal-id", required=True, help="Bugout.dev journal ID")
        parser.add_argument(
            "--interval-minutes",
            type=int,
            required=False,
            default=1440,  # once a day
            help="Export interval (minutes)",
        )
