# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.conf import settings
from django.core.management.base import BaseCommand

from toolchain.buildsense.search.indexes_manager import BuildsenseIndexManager


class Command(BaseCommand):
    help = "Create the Elasticsearch Index for BuildSense/Pants data"

    def handle(self, *args, **options):
        mgr = BuildsenseIndexManager.for_django_settings(settings)
        mgr.create_index()
