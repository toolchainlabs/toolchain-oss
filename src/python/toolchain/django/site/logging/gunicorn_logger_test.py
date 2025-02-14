# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging

import pytest

from toolchain.django.site.logging.gunicorn_logger import ChecksFilter


@pytest.mark.parametrize(
    ("message", "should_log"),
    [
        ('GET /metricsz HTTP/1.1" 200 31178 "-" "Prometheus/2.7.1', 0),
        ('GET /healthz HTTP/1.1" 200 2 "-" "ELB-HealthChecker/2.0', 0),
        ('GET /healthz HTTP/1.1" 200 2 "-" "kube-probe/1.14+', 0),
        (
            'GET /api/v1/users/me/ HTTP/1.1" 200 190 "https://staging.app.toolchain.com/" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.120 Safari/537.36',
            1,
        ),
        (
            'GET /healthz HTTP/1.1" 200 2 "-" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.120 Safari/537.36',
            1,
        ),
        (
            'GET /api/v1/users/me/ HTTP/1.1" 200 80 "https://staging.app.toolchain.com/" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.70 Safari/537.36',
            1,
        ),
    ],
)
def test_filter_healthchecks(message: str, should_log: int) -> None:
    logging_filter = ChecksFilter("costanza")
    record = logging.LogRecord(
        name="jerry-log", level=logging.INFO, pathname="soup", lineno=77, msg=message, args=tuple(), exc_info=None
    )
    assert logging_filter.filter(record) == should_log
