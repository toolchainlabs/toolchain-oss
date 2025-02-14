# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.conf import settings
from django.core.management.base import BaseCommand

from toolchain.buildsense.search.indexes_manager import BuildsenseIndexManager


class Command(BaseCommand):
    help = "Update buildsense ES index alias to use the new (lastest) index."

    def handle(self, *args, **options):
        mgr = BuildsenseIndexManager.for_django_settings(settings)
        mgr.update_alias()
