# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime

from django.conf import settings
from django.contrib.sitemaps import Sitemap

from toolchain.pants_demos.depgraph.models import DemoRepo
from toolchain.pants_demos.depgraph.utils import get_url_for_repo


class DemoReposSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.5

    def items(self):
        return DemoRepo.get_successful_qs(excludes=settings.REPOS_DISABLE_INDEXING)

    def lastmod(self, item: DemoRepo) -> datetime.datetime:
        return item.last_processed

    def get_latest_lastmod(self):
        return self.items().latest("-last_processed").last_processed

    def location(self, item: DemoRepo):
        return get_url_for_repo(item)
