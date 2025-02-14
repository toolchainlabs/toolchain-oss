# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.core.management.base import BaseCommand

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.crawler.pypi.models import PeriodicallyUpdateLevelDb
from toolchain.django.db.transaction_broker import TransactionBroker


class Command(BaseCommand):
    help = "Set LevelDBs update frequency."
    MIN_INTERVAL_MIN = 20
    MAX_INTERVAL_MIN = 680

    def handle(self, *args, **options):
        period_minutes = int(options["minutes"])
        if period_minutes > self.MAX_INTERVAL_MIN or period_minutes < self.MIN_INTERVAL_MIN:
            raise ToolchainAssertion(
                f"LevelDB update frequency should be more than {self.MIN_INTERVAL_MIN}m and less than {self.MIN_INTERVAL_MIN}m."
            )
        with TransactionBroker("crawlerpypi").atomic():
            qs = PeriodicallyUpdateLevelDb.objects.filter(period_minutes__isnull=False)
            for puldb in qs:
                puldb.period_minutes = period_minutes
                puldb.save()

    def add_arguments(self, parser):
        parser.add_argument("--minutes", required=True, help="Crawl frequency (in minutes)")
