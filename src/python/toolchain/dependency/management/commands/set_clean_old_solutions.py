# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.core.management.base import BaseCommand

from toolchain.dependency.models import PeriodicallyCleanOldSolutions


class Command(BaseCommand):
    help = "Set resolver solutions cleanup parameters."

    def handle(self, *args, **options):
        period_minutes = int(options["minutes"])
        threshold_days = int(options["threshold"])
        PeriodicallyCleanOldSolutions.create_or_update(period_minutes=period_minutes, threshold_days=threshold_days)

    def add_arguments(self, parser):
        parser.add_argument("--minutes", required=True, help="Cleanup run internval (in minutes)")
        parser.add_argument("--threshold", required=True, help="Clean solution older than X days")
