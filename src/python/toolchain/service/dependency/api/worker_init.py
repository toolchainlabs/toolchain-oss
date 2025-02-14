# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.conf import settings


def start_reloader():
    settings.DEPGRAPH.start()
    settings.MODULE_DISTRIBUTION_MAP.start()
