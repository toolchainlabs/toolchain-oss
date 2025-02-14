# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime

from dateutil.parser import parse
from django.core.management.base import BaseCommand

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.crawler.pypi.models import ProcessDistribution
from toolchain.workflow.models import WorkUnit


class Command(BaseCommand):
    help = "Reprocess all distributions that last ran in a given date range."

    def _parse_dt(self, dt_str: str, allow_empty: bool):
        if not dt_str:
            if not allow_empty:
                raise ToolchainAssertion("Missing date data.")
            return None
        dt = parse(dt_str)
        if dt.tzinfo:
            raise ToolchainAssertion("Dates are UTC, don't provide TZ info")
        return dt.replace(tzinfo=datetime.timezone.utc)

    def handle(self, *args, **options):
        from_date = self._parse_dt(options["from"], allow_empty=False)
        to_date = self._parse_dt(options["to"], allow_empty=True) or utcnow()
        WorkUnit.rerun_all(ProcessDistribution, from_date=from_date, to_date=to_date)

    def add_arguments(self, parser):
        parser.add_argument("--from", required=True, help="From date (UTC)")
        parser.add_argument("--to", required=False, default=None, help="To date (UTC) defaults to now.")
