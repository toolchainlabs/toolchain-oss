# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json
from urllib.parse import parse_qsl, urlparse

import pkg_resources

from toolchain.util.prod.pagerduty import ToolchainPagerDutyClient


def load_fixture(fixture: str) -> dict:
    return json.loads(pkg_resources.resource_string(__name__, f"fixtures/{fixture}.json"))


def add_service_response(responses, service: str, integration: str) -> None:
    fixture = load_fixture("pagerduty_services")
    fixture["services"][0]["name"] = service
    fixture["services"][0]["integrations"][0]["name"] = integration
    responses.add(responses.GET, "https://api.pagerduty.com/services", json=fixture)


def add_pagerduty_response(responses, path: str, fixture_name: str) -> None:
    fixture = load_fixture(fixture_name)
    responses.add(responses.GET, f"https://api.pagerduty.com/{path}", json=fixture)


class TestToolchainPagerDutyClient:
    def test_get_integration_details(self, responses) -> None:
        add_pagerduty_response(responses, "services", "pagerduty_services")
        client = ToolchainPagerDutyClient("Gold jerry!! Gold")
        integration_details = client.get_integration_details(
            service_name="feats-of-strength", integration_name="aluminum-pole"
        )
        assert integration_details.key == "SOUP"
        assert integration_details.url == "https://events.pagerduty.com/v2/enqueue"
        assert len(responses.calls) == 1
        request = responses.calls[0].request
        params = dict(parse_qsl(urlparse(request.url).query))
        assert params == {"limit": "100", "query": "feats-of-strength", "include[]": "integrations", "offset": "0"}
        assert request.url.startswith("https://api.pagerduty.com/services?")
        assert request.headers["Authorization"] == "Token token=Gold jerry!! Gold"
