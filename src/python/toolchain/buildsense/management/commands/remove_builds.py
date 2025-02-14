# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from toolchain.buildsense.ingestion.scripts.builds_remover import BuildsRemover

_logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Remove builds based on a s3 path"

    def add_arguments(self, parser):
        parser.add_argument("--no-dry-run", action="store_true", required=False, default=False, help="Dry run.")
        parser.add_argument("--path", required=True, help="s3 path prefix (customer & repo)")

    def handle(self, *args, **options):
        prefix = options["path"]
        dry_run = not options["no_dry_run"]
        remover = BuildsRemover.for_django_command(django_settings=settings, dry_run=dry_run)
        count = remover.delete_builds_for_key(prefix=prefix)
        _logger.info(f"Builds removed: {count}")
