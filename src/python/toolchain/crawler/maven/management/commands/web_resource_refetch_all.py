# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.core.management.base import BaseCommand

from toolchain.crawler.base.models import FetchURL
from toolchain.workflow.models import WorkUnit


# Reminder that Django requires this class to be named 'Command'.
# The command name is the module name.
class Command(BaseCommand):
    help = "Force re-fetching of all web resources."

    def handle(self, *args, **options):
        WorkUnit.rerun_all(FetchURL)
