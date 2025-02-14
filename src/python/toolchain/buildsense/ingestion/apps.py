# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.apps import AppConfig


class BuildDataIngestionAppConfig(AppConfig):
    name = "toolchain.buildsense.ingestion"
    label = "ingestion"
    verbose_name = "Build Data Ingestion"
