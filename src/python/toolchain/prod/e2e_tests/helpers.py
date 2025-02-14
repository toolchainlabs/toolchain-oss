# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime
import logging
import socket
import time

import pytest

_logger = logging.getLogger(__name__)


def wait_for_host(host_name: str, timeout_min: int = 7) -> None:
    threshold = time.time() + datetime.timedelta(minutes=timeout_min).total_seconds()
    _logger.info(f"Resolve {host_name=}")
    while True:
        try:
            socket.gethostbyname_ex(host_name)
        except socket.gaierror as err:
            remaining = threshold - time.time()
            if remaining < 0:
                pytest.fail(f"Failed to resolve {host_name} {err!r}")
            _logger.warning(f"wait_for_host {host_name} - remaining {int(remaining)} seconds. error: {err!r}")
            time.sleep(10)
        else:
            return
