# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from dataclasses import astuple

import pytest

from toolchain.crawler.pypi.xmlrpc_api import ApiClient

# Note: These tests query the live PyPI XMLRPC API directly.
# If PyPI is down then we don't expect anything to work anyway...
# We do get throttled by pypi, so those tests are slow because we use a rate limiter.


@pytest.mark.skip(reason="pypi has disabled XML RPC APIs")
def test_get_last_serial() -> None:
    assert ApiClient().get_last_serial() > 5838400  # The last serial at the time of writing this test.


@pytest.mark.skip(reason="pypi has disabled XML RPC APIs")
def test_get_changed_packages() -> None:
    change_log = ApiClient().get_changed_packages(5837575, 5837585)

    assert [astuple(entry) for entry in change_log.added] == [
        ("bake-cli", "0.2.1", "bake-cli-0.2.1.tar.gz", 5837575),
        ("airduct", "0.1.13", "airduct-0.1.13-py3-none-any.whl", 5837577),
        ("airduct", "0.1.13", "airduct-0.1.13.tar.gz", 5837578),
        ("magenta", "1.1.5", "magenta-1.1.5-py2.py3-none-any.whl", 5837582),
        ("fronts", "0.9.2", "fronts-0.9.2.tar.gz", 5837584),
    ]
    assert [astuple(entry) for entry in change_log.removed] == [("reclib", "0.2.0", "reclib-0.2.0.tar.gz", 5837579)]
