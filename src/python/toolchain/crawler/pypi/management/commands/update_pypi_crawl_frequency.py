# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.core.management.base import BaseCommand

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.crawler.pypi.models import PeriodicallyProcessChangelog
from toolchain.django.db.transaction_broker import TransactionBroker


class Command(BaseCommand):
    help = "Update pypi crawl frequency."
    MIN_INTERVAL_MIN = 20
    MAX_INTERVAL_MIN = 680

    def handle(self, *args, **options):
        period_minutes = int(options["minutes"])
        if period_minutes > self.MAX_INTERVAL_MIN or period_minutes < self.MIN_INTERVAL_MIN:
            raise ToolchainAssertion(
                f"Crawl period should be more than {self.MIN_INTERVAL_MIN}m and less than {self.MIN_INTERVAL_MIN}m."
            )
        if PeriodicallyProcessChangelog.objects.count() > 1:
            raise ToolchainAssertion("More than one PeriodicallyProcessChangelog objects is not supported.")
        with TransactionBroker("crawlerpypi").atomic():
            ppc = PeriodicallyProcessChangelog.objects.first()
            ppc.period_minutes = period_minutes
            ppc.save()

    def add_arguments(self, parser):
        parser.add_argument("--minutes", required=True, help="Crawl frequency (in minutes)")
