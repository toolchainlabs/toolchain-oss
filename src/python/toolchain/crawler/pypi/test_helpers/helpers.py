# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
from functools import wraps
from unittest import mock
from xmlrpc.client import ProtocolError

import pkg_resources


def load_fixture(fixture_name: str):
    return json.loads(pkg_resources.resource_string(__name__, f"fixtures/{fixture_name}.json"))


_SERVER_PROXY = "toolchain.crawler.pypi.xmlrpc_api.RateLimitedServerProxy"


def mock_changelog_since_serial(fixture: str):
    def decorator_wrapper(func):
        @wraps(func)
        def wrapper(*args, **kwds):
            with mock.patch(_SERVER_PROXY) as mock_proxy_ctor:
                mock_proxy = mock.MagicMock()
                mock_proxy.changelog_since_serial.return_value = load_fixture(fixture)
                mock_proxy_ctor.return_value = mock_proxy
                return func(*args, **kwds)

        return wrapper

    return decorator_wrapper


def mock_changelog_since_serial_error(error_message: str):
    def decorator_wrapper(func):
        @wraps(func)
        def wrapper(*args, **kwds):
            with mock.patch(_SERVER_PROXY) as mock_proxy_ctor:
                mock_proxy = mock.MagicMock()
                mock_proxy.changelog_since_serial.side_effect = ProtocolError(
                    url="pypi.org/pypi", errcode=503, errmsg=error_message, headers={}
                )
                mock_proxy_ctor.return_value = mock_proxy
                return func(*args, **kwds)

        return wrapper

    return decorator_wrapper


def add_project_response(responses, headers: dict[str, str], project: str, fixture: str | None = None) -> None:
    responses.add(
        responses.GET,
        url=f"https://pypi.org/pypi/{project}/json",
        json=load_fixture(fixture or project),
        adding_headers=headers,
    )


def add_projects_responses(responses, last_serial: int, *projects: str) -> None:
    headers = {"X-PYPI-LAST-SERIAL": str(last_serial)} if last_serial else {}
    for project in projects:
        add_project_response(responses, headers=headers, project=project)
