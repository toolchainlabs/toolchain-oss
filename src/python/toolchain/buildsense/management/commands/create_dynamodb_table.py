# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.core.management.base import BaseCommand

from toolchain.buildsense.ingestion.run_info_table import RunInfoTable


class Command(BaseCommand):
    help = "Create the RunInfo DynamoDB table."

    def handle(self, *args, **options):
        RunInfoTable.create_table()
