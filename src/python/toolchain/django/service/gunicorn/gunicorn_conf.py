# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
import os as _os  # Renamed so it's not imported by service-specific configs that import * this module.

from prometheus_client import multiprocess

from toolchain.util.constants import REQUEST_ID_HEADER

_logger = logging.getLogger(__name__)


"""Default gunicorn config.

Service-specific configs can import * and override as needed.
"""

bind = "0.0.0.0:8001"
accesslog = "-"
errorlog = "-"
loglevel = _os.environ.get("LOG_LEVEL", "INFO").lower()
timeout = 120
# TODO: Consider 'gthread' or http://docs.gunicorn.org/en/stable/design.html#asyncio-workers.
worker_class = "sync"
# Tune on a per-service basis.  2xcores+1 is a generally accepted good number.
# But note that too many sync workers can lead to thrashing and OOM.
workers = 3
preload_app = True
pidfile = "/var/run/gunicorn/master.pid"
# https://docs.gunicorn.org/en/stable/settings.html#access-log-format
access_log_format = f'%(l)s %(t)s %({{{REQUEST_ID_HEADER.lower()}}}i)s %({{remote-user}}i)s "%(m)s %(U)s" %(s)s %(b)s "%(f)s" "%(M)s "%(a)s""'
# TODO: add the user once the GunicornLogger is updated to extract that info from the request (in JWT/Custom internal headers)
# access_log_format = '%(h)s %(l)s %(t)s "%(m)s %(U)s" %(s)s %(b)s "%(f)s" "%(a)s"'
logger_class = "toolchain.django.site.logging.gunicorn_logger.GunicornLogger"
limit_request_line = 8190  # The maximum value allowed other than 0 for unlimited.
# Limiting the number of requests to work around memory issues in pypi crawler.
# see https://github.com/toolchainlabs/toolchain/pull/3041
max_requests = 50000  # (50K requests.)


def child_exit(server, worker):
    multiprocess.mark_process_dead(worker.pid)
    _logger.info(f"gunicorn child_exit. pid={worker.pid}")
