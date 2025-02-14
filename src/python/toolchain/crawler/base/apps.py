# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.apps import AppConfig


class CrawlerBaseAppConfig(AppConfig):
    name = "toolchain.crawler.base"
    label = "crawlerbase"
    verbose_name = "Base crawler functionality"
