# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.core.management.base import BaseCommand

from toolchain.users.models import PeriodicallyNotifyExpringTokens


class Command(BaseCommand):
    help = "Configures expiring CI tokens notification workflow"

    def handle(self, *args, **options) -> None:
        interval = options["interval_minutes"]
        PeriodicallyNotifyExpringTokens.create_or_update(period_minutes=interval)

    def add_arguments(self, parser):
        parser.add_argument(
            "--interval-minutes",
            type=int,
            required=False,
            default=1440,  # once a day
            help="Export interval (minutes)",
        )
