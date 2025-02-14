# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.django.service.gunicorn.gunicorn_conf import *  # noqa: F401, F403

# Most API calls are network i/o bound - read/write from AWS s3
# which is is can be slow at times (up to a few hundreds of msec)
# having more workers/threads is better in this type of workload.
workers = 6
