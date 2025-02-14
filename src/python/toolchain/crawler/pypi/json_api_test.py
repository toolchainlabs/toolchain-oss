# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest
from requests.exceptions import ConnectionError, ConnectTimeout, TooManyRedirects

from toolchain.crawler.pypi.exceptions import NoProjectData, StaleResponse, TransientError
from toolchain.crawler.pypi.json_api import get_project_data, purge
from toolchain.crawler.pypi.test_helpers.helpers import load_fixture


@pytest.mark.withoutresponses()
def test_get_project_data() -> None:
    # Note: queries the live PyPI JSON API directly. If PyPI is down then we don't expect anything to work anyway.
    # In a case of a partial pypi outage, get_project_data will raise a StaleResponse since the header indicating the last serial will be missing.
    # Check out the pypi status page at: https://status.python.org/
    dists = get_project_data("sampleproject", 5328000)
    assert len(dists["1.2.0"]) == 2
    assert dists["1.2.0"][0]["filename"] == "sampleproject-1.2.0-py2.py3-none-any.whl"
    assert dists["1.2.0"][1]["filename"] == "sampleproject-1.2.0.tar.gz"


def _assert_purge_request(call, project: str) -> None:
    assert call.request.method == "PURGE"
    assert call.request.url == f"https://pypi.org/pypi/{project}/json"


def test_purge_ok(
    responses,
) -> None:
    responses.add("PURGE", "https://pypi.org/pypi/mandelbaum/json")
    purge("mandelbaum")
    assert len(responses.calls) == 1
    _assert_purge_request(responses.calls[0], "mandelbaum")


def test_purge_http_failure(responses, caplog) -> None:
    responses.add("PURGE", "https://pypi.org/pypi/mandelbaum/json", status=503)
    purge("mandelbaum")
    assert len(responses.calls) == 1
    _assert_purge_request(responses.calls[0], "mandelbaum")
    assert "Attempt to PURGE https://pypi.org/pypi/mandelbaum/json failed with" in caplog.records[-1].message


def test_purge_connection_failure(responses, caplog) -> None:
    responses.add("PURGE", "https://pypi.org/pypi/mandelbaum/json", body=ConnectTimeout("It's go time"))
    purge("mandelbaum")
    assert len(responses.calls) == 1
    _assert_purge_request(responses.calls[0], "mandelbaum")
    assert "Attempt to PURGE https://pypi.org/pypi/mandelbaum/json failed with" in caplog.records[-1].message


class TestGetProjectData:
    def test_no_project_datas(self, responses) -> None:
        responses.add(responses.GET, "https://pypi.org/pypi/no-soup-for-you/json", status=404)
        with pytest.raises(NoProjectData, match="404 https://pypi.org/pypi/no-soup-for-you/json"):
            get_project_data("no-soup-for-you", 77112)
        assert len(responses.calls) == 1

    def test_stale_response(self, responses) -> None:
        responses.add(
            responses.GET,
            url="https://pypi.org/pypi/pythonslm/json",
            json=load_fixture("pythonslm"),
            adding_headers={"X-PYPI-LAST-SERIAL": str(1_000_000)},
        )

        with pytest.raises(
            StaleResponse,
            match="Expected page to have at least serial 10000002 but it had 1000000: https://pypi.org/pypi/pythonslm/json",
        ):
            get_project_data("pythonslm", 1_000_0002)

    def test_missing_last_serial_response(self, responses) -> None:
        responses.add(responses.GET, url="https://pypi.org/pypi/pythonslm/json", json=load_fixture("pythonslm"))

        with pytest.raises(StaleResponse, match="Missing X-PYPI-LAST-SERIAL headers"):
            get_project_data("pythonslm", 1_000_0002)

    @pytest.mark.parametrize("error_cls", [ConnectionError, TooManyRedirects])
    def test_request_error(self, responses, error_cls) -> None:
        responses.add(responses.GET, "https://pypi.org/pypi/no-soup-for-you/json", body=error_cls("It's go time."))
        with pytest.raises(TransientError, match="Failed to get project data.*It's go time"):
            get_project_data("no-soup-for-you", 77112)
        assert len(responses.calls) == 1
