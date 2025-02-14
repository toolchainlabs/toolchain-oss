# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.core.management.base import BaseCommand

from toolchain.crawler.pypi.models import DumpDistributionData
from toolchain.django.db.transaction_broker import TransactionBroker

transaction = TransactionBroker("crawlerpypi")


class Command(BaseCommand):
    help = "Trigger a full data dump."

    def add_arguments(self, parser):
        parser.add_argument("--num-shards", type=int, choices=(16, 256), default=256)
        parser.add_argument("--concurrency", type=int, default=1)

    def handle(self, *args, **options):
        DumpDistributionData.trigger_full(num_shards=options["num_shards"], concurrency=options["concurrency"])
