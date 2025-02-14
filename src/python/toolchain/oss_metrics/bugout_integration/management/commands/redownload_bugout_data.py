# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime

from dateutil.rrule import DAILY, rrule
from django.core.management.base import BaseCommand

from toolchain.base.datetime_tools import utcnow
from toolchain.oss_metrics.bugout_integration.models import DownloadBugoutDataForDay


class Command(BaseCommand):
    help = "Trigger bugout data download for a given date range."

    def handle(self, *args, **options) -> None:
        journal_id = options["journal_id"]
        from_date = datetime.date.fromisoformat(options["from_date"])
        to_date_str = options["to_date"]
        to_date = datetime.date.fromisoformat(to_date_str) if to_date_str else utcnow().date()
        for day in rrule(DAILY, dtstart=from_date, until=to_date):
            DownloadBugoutDataForDay.run_for_date(day=day, journal_id=journal_id)

    def add_arguments(self, parser):
        parser.add_argument("--journal-id", required=True, help="Bugout.dev journal ID")
        parser.add_argument("--from-date", required=True, help="From date (dd/mm/yyyy)")
        parser.add_argument("--to-date", required=False, help="To date (dd/mm/yyyy)")
