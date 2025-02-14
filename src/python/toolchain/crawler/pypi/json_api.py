# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
from typing import Any

import requests

from toolchain.crawler.pypi.exceptions import NoProjectData, StaleResponse, TransientError
from toolchain.lang.python.distributions.distribution_key import canonical_project_name

_logger = logging.getLogger(__name__)


JSON_API_URL_PREFIX = "https://pypi.org/pypi"

ProjectData = dict[str, list[dict[str, Any]]]


def get_project_data(project: str, required_serial: int) -> ProjectData:
    """Get data about the specified project from the PyPI JSON API."""
    project = canonical_project_name(project)
    url = _url_for_project(project)
    try:
        response = requests.get(url)
    except requests.RequestException as error:
        _logger.warning(f"Failed to get project data: {url} {error!r}", exc_info=True)
        raise TransientError(f"Failed to get project data: {url} {error!r}")
    if not response.ok:
        _logger.info(f"NoProjectData: {project=} {required_serial=} status_code={response.status_code} {url=}")
        raise NoProjectData(f"{response.status_code} {url}")
    if "X-PYPI-LAST-SERIAL" not in response.headers:
        raise StaleResponse(f"Missing X-PYPI-LAST-SERIAL headers. headers={response.headers}")
    server_serial = int(response.headers["X-PYPI-LAST-SERIAL"])
    if server_serial < required_serial:
        raise StaleResponse(
            f"Expected page to have at least serial {required_serial} but it had {server_serial}: {url}"
        )
    return response.json().get("releases", {})


def purge(project: str) -> None:
    """Ask the server to purge a stale cached response for the project's data."""
    project = canonical_project_name(project)
    url = _url_for_project(project)
    try:
        response = requests.request("PURGE", url)
        response.raise_for_status()
    except requests.exceptions.RequestException as ex:
        _logger.exception(f"Attempt to PURGE {url} failed with: {ex!r}")


def _url_for_project(project: str) -> str:
    return f"{JSON_API_URL_PREFIX}/{project}/json"
