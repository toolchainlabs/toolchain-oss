# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.core.management.base import BaseCommand

from toolchain.crawler.base.models import FetchURL


# Reminder that Django requires this class to be named 'Command'.
# The command name is the module name.
class Command(BaseCommand):
    help = "Seed the crawl with initial metadata pages."

    # TODO: Figure out what we really want to use for seeding.
    # Meanwhile, this was useful for testing and kicking the tires.
    SEED_URLS = ["https://repo1.maven.org/maven2/com/fasterxml/jackson/"]

    def handle(self, *args, **options):
        for url in self.SEED_URLS:
            FetchURL.get_or_create(url=url)

    def _schedule(self):
        pass
