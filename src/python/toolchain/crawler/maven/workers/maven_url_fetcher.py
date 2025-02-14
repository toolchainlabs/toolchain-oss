# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import requests
from django.conf import settings

from toolchain.crawler.base.url_fetcher import URLFetcher
from toolchain.crawler.maven.maven_schedule_util import MavenScheduleUtil


class MavenURLFetcher(URLFetcher):
    schedule_util_cls = MavenScheduleUtil

    def get_expected_hash(self, web_resource):
        if not settings.VERIFY_SHA1S:
            return None, None

        sha1_url = f"{web_resource.url}.sha1"
        # In real-world .sha1 files, the sha1 is sometimes the entire content of the file,
        # and sometimes it's the first token in a space-separated pair, where the second
        # token is the file name.  This split() stanza covers both cases.
        expected_hash_hexdigest = requests.get(sha1_url).text.split()[0]
        return self.SHA1, expected_hash_hexdigest

    def schedule_processing_work(self, web_resource, changed):
        if not changed:
            return

        def noop(wr):
            pass

        def schedule_fetch(wr):
            self.schedule_util.schedule_fetch(wr.url)

        # Note that order matters: The first suffix match will be applied.
        suffix_to_schedule_func = (
            ("/", self.schedule_util.schedule_link_page_processing),
            ("/maven-metadata.xml", self.schedule_util.schedule_maven_metadata_processing),
            (".pom", self.schedule_util.schedule_extract_pom_info),
        ) + (
            (
                ("-javadoc.jar", noop),  # So we don't match .jar below.
                ("-sources.jar", schedule_fetch),
                (".jar", schedule_fetch),
            )
            if settings.DOWNLOAD_JARS
            else tuple()
        )

        for suffix, schedule_func in suffix_to_schedule_func:
            if web_resource.url.endswith(suffix):
                schedule_func(web_resource)
                break
