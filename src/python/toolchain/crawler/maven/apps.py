# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.apps import AppConfig


class CrawlerMavenAppConfig(AppConfig):
    name = "toolchain.crawler.maven"
    label = "crawlermaven"
    verbose_name = "A crawler for Maven data"
