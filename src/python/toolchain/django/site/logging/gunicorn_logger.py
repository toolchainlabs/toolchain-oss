# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging

from gunicorn import glogging


class ChecksFilter(logging.Filter):
    """Log filter that drops requests health checks from kubernetes and AWS ELB and promethus metrics scraping."""

    _FILTER_ON = ["kube-probe", "Prometheus/", "ELB-HealthChecker"]

    def filter(self, record):
        message = record.getMessage()
        for part in self._FILTER_ON:
            if part in message:
                return 0
        return 1


class GunicornLogger(glogging.Logger):
    """Custom gunicorn logger class that filters logs we don't want."""

    def setup(self, cfg):
        super().setup(cfg)
        self.access_log.addFilter(ChecksFilter())
