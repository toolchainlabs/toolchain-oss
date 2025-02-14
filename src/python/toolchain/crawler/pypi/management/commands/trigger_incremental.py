# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import argparse

from django.core.management.base import BaseCommand

from toolchain.crawler.pypi.models import PeriodicallyProcessChangelog
from toolchain.django.db.transaction_broker import TransactionBroker

transaction = TransactionBroker("crawlerpypi")


def _optional_positive_int(value):
    if value is None:
        return None
    ivalue = int(value)
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(f"Invalid positive integer: {ivalue}")
    return ivalue


class Command(BaseCommand):
    help = "Trigger an incremental crawl."

    def add_arguments(self, parser):
        parser.add_argument(
            "--period-minutes",
            type=_optional_positive_int,
            default=None,
            help="The crawl will repeat every this number of minutes.  If unspecified, the crawl "
            "will be run just once and will not repeat.",
        )

    def handle(self, *args, **options):
        PeriodicallyProcessChangelog.objects.create(period_minutes=options["period_minutes"])
