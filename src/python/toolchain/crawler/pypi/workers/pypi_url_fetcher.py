# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging

from toolchain.crawler.base.schedule_util import ScheduleUtil
from toolchain.crawler.base.url_fetcher import URLFetcher
from toolchain.packagerepo.pypi.util import PYTHON_HOSTED_URL, extract_digest

logger = logging.getLogger(__name__)


class PypiURLFetcher(URLFetcher):
    schedule_util_cls = ScheduleUtil

    def get_expected_hash(self, web_resource):
        url = web_resource.url
        if url.startswith(PYTHON_HOSTED_URL):
            return self.SHA256, extract_digest(url)
        return None, None

    def schedule_processing_work(self, web_resource, changed):
        # We currently use this URLFetcher exclusively to fetch distributions, which never change for a given URL.
        # This means that the ProcessDistribution work doesn't need to reference a specific version of a URL,
        # meaning we can (and do) pre-schedule it when we schedule the FetchURL work.
        # Therefore we don't need to do any further scheduling here.
        pass
