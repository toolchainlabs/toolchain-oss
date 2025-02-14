# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.core.management.base import BaseCommand

from toolchain.base.datetime_tools import utcnow
from toolchain.crawler.pypi.models import ProcessAllProjects
from toolchain.crawler.pypi.xmlrpc_api import ApiClient


class Command(BaseCommand):
    help = "Trigger a full crawl."

    def handle(self, *args, **options):
        ProcessAllProjects.objects.create(created_at=utcnow(), serial=ApiClient().get_last_serial(), num_shards=1000)
