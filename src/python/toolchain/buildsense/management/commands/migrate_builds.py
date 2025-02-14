# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from toolchain.buildsense.ingestion.scripts.builds_mover import BuildsMover

_logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Migrate builds between Repos"

    def add_arguments(self, parser):
        parser.add_argument("--no-dry-run", action="store_true", required=False, default=False, help="Dry run.")
        parser.add_argument("--src-repo-slug", required=True, help="Source repo slug")
        parser.add_argument("--tgt-repo-slug", required=False, help="Target repo slug")

    def handle(self, *args, **options):
        src_repo_slug = options["src_repo_slug"]
        tgt_repo_slug = options["tgt_repo_slug"]
        dry_run = not options["no_dry_run"]
        mover = BuildsMover.for_django_command(django_settings=settings, dry_run=dry_run)
        total_count, migrated_count = mover.move_builds(src_repo_slug=src_repo_slug, tgt_repo_slug=tgt_repo_slug)
        _logger.info(f"Total keys: {total_count} migrated: {migrated_count}")
