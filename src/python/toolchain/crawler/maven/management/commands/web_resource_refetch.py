# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.core.management.base import BaseCommand

from toolchain.crawler.base.models import FetchURL
from toolchain.django.db.transaction_broker import TransactionBroker
from toolchain.workflow.models import WorkUnit

transaction = TransactionBroker("crawlermaven")


# Reminder that Django requires this class to be named 'Command'.
# The command name is the module name.
class Command(BaseCommand):
    help = "Force web resource fetching to re-run for given seed urls."

    SEED_URLS = ["https://repo1.maven.org/maven2/com/fasterxml/jackson/"]

    def handle(self, *args, **options):
        for url in self.SEED_URLS:
            with transaction.atomic():
                payload = FetchURL.get_or_create(url=url)
                locked_wu = WorkUnit.locked(payload.pk)
                locked_wu.rerun()
                locked_wu.save()
