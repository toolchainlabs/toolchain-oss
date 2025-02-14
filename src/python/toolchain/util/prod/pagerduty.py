# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from dataclasses import dataclass

from pdpyras import APISession

from toolchain.base.toolchain_error import ToolchainAssertion

# https://developer.pagerduty.com/api-reference/b3A6Mjc0ODI2Nw-send-an-event-to-pager-duty
GENERIC_INTEGRATION_URL = "https://events.pagerduty.com/v2/enqueue"


@dataclass(frozen=True)
class Integration:
    url: str
    key: str

    @classmethod
    def from_json(cls, json_dict: dict) -> Integration:
        return cls(url=GENERIC_INTEGRATION_URL, key=json_dict["integration_key"])


class ToolchainPagerDutyClient:
    def __init__(self, api_token: str) -> None:
        self._session = APISession(api_token)

    def get_service_by_name(self, name: str) -> dict:
        services_iter = self._session.iter_all("services", params={"query": name, "include[]": "integrations"})
        for service in services_iter:
            if service["name"] == name:
                return service
        raise ToolchainAssertion(f"Can't find service '{name}'")

    def get_integration_details(self, *, service_name: str, integration_name: str) -> Integration:
        service = self.get_service_by_name(service_name)
        for integration in service["integrations"]:
            if integration["name"] == integration_name:
                return Integration.from_json(integration)
        raise ToolchainAssertion(f"Can't find integration '{integration_name}' for service '{service_name}'")
