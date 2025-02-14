# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.core.management.base import BaseCommand

from toolchain.oss_metrics.bugout_integration.models import DownloadBugoutDataForDay
from toolchain.oss_metrics.models import UpsertPantsTelemetryForDay


class Command(BaseCommand):
    help = "Configure upsert data into influxdb based on existing bugout data download."

    def handle(self, *args, **options) -> None:
        journal_id = options["journal_id"]
        qs = DownloadBugoutDataForDay.objects.filter(journal_id=journal_id)
        for dl_data in qs:
            upsert = UpsertPantsTelemetryForDay.run_for_date(day=dl_data.day, journal_id=journal_id)
            upsert.add_requirement_by_id(dl_data.work_unit_id)
        self.stdout.write(self.style.NOTICE(f"Added {qs.count()} upsert commands for {journal_id=}."))

    def add_arguments(self, parser):
        parser.add_argument("--journal-id", required=True, help="Bugout.dev journal ID")
