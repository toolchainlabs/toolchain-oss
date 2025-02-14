# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.apps import AppConfig


class CrawlerPypiAppConfig(AppConfig):
    name = "toolchain.crawler.pypi"
    label = "crawlerpypi"
    verbose_name = "A crawler for pypi data"
