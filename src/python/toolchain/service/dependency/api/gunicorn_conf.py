# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging

from toolchain.django.service.gunicorn.gunicorn_conf import *  # noqa: F401, F403
from toolchain.service.dependency.api.worker_init import start_reloader

preload_app = False

_logger = logging.getLogger(__name__)


def post_worker_init(worker):
    _logger.info(f"gunicorn post_worker_init. pid={worker.pid}")
    start_reloader()
