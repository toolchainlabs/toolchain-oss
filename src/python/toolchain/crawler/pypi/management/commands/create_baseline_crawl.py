# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime

from django.core.management.base import BaseCommand

from toolchain.base.datetime_tools import utcnow
from toolchain.crawler.pypi.models import ProcessAllProjects
from toolchain.django.db.transaction_broker import TransactionBroker

transaction = TransactionBroker("workflow")


class Command(BaseCommand):
    """Creates a fake crawl state.

    This is useful when we want to copy crawl artifacts (packagerepopypi_*, webresources_* tables and S3 artifacts) from
    one environment to another want to continue the crawl from the last point we have crawled to in the source
    environment.
    """

    help = "Creates baseline crawl fake state that we will crawl from"

    def add_arguments(self, parser):
        parser.add_argument("--serial", type=int, required=True, help="The pypi serial we crawled up to.")

    def handle(self, *args, **options):
        now = utcnow()
        with transaction.atomic():
            payload = ProcessAllProjects.objects.create(num_shards=1, serial=options["serial"], created_at=now)
            workunit = payload.work_unit
            workunit.take_lease(until=now + datetime.timedelta(hours=1), last_attempt=now, node="command")
            workunit.work_succeeded()
