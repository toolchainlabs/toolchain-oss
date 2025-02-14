# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
from dataclasses import dataclass

import httpx

from toolchain.payments.stripe_integration.client.common import get_http_client


@dataclass(frozen=True)
class PlanAndUsage:
    plan: str
    price: str
    trial_end: datetime.date | None
    cache_read_bytes: int | None
    cache_write_bytes: int | None


class PaymentsCustomerClient:
    @classmethod
    def for_customer(cls, django_settings, *, customer_id: str) -> PaymentsCustomerClient:
        client = get_http_client(django_settings, url_prefix=f"/internal/api/v1/customers/{customer_id}/")
        return cls(client=client, customer_id=customer_id)

    def __init__(self, *, client: httpx.Client, customer_id: str) -> None:
        self._client = client
        self._customer_id = customer_id

    def get_plan_and_usage(self) -> PlanAndUsage:
        response = self._client.get("info/")
        response.raise_for_status()
        resp_json = response.json()
        plan_json = resp_json["plan"]
        trial_end_str = plan_json.get("trial_end")
        usage_json = resp_json["usage"]
        return PlanAndUsage(
            plan=plan_json.get("name", "N/A"),
            price=plan_json.get("price", "N/A"),
            trial_end=datetime.date.fromisoformat(trial_end_str) if trial_end_str else None,
            cache_read_bytes=usage_json.get("read_bytes"),
            cache_write_bytes=usage_json.get("write_bytes"),
        )
