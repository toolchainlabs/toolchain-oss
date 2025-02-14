# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from django.core.management.base import BaseCommand

from toolchain.oss_metrics.metrics_store import AnonymousTelemetryMetricStoreManager


class Command(BaseCommand):
    help = "Create buckets in influxdb"

    def add_arguments(self, parser):
        parser.add_argument(
            "--recreate",
            type=bool,
            required=False,
            default=False,
            help="Recreate buckets if they already exist",
        )

    def handle(self, *args, **options):
        recreate_buckets = options["recreate"]
        AnonymousTelemetryMetricStoreManager.init_buckets(recreate=recreate_buckets)
