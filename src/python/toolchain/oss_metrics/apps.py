# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.apps import AppConfig


class OssMetricsAppConfig(AppConfig):
    name = "toolchain.oss_metrics"
    label = "oss_metrics"
    verbose_name = "Pants Project OSS Metrics"
