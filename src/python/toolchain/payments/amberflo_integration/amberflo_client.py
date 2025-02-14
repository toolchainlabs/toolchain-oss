# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass

import httpx

from toolchain.base.toolchain_error import ToolchainAssertion, ToolchainTransientError
from toolchain.payments.amberflo_integration.config import AmberFloConfiguration

_logger = logging.getLogger(__name__)


class AmberfloTransientError(ToolchainTransientError):
    """Raised on transient errors communcating with the amberflo API."""

    def __init__(self, call_name: str, msg: str) -> None:
        self._call_name = call_name
        super().__init__(msg)

    @property
    def call_name(self) -> str:
        return self._call_name


@dataclass(frozen=True)
class AmberfloCustomer:
    customer_id: str
    name: str
    update_time: datetime.datetime


@dataclass(frozen=True)
class CustomerMetrics:
    read_bytes: int
    write_bytes: int
    num_read_blobs: int
    num_write_blobs: int

    @classmethod
    def from_dict(cls, metrics_dict: dict[str, int]) -> CustomerMetrics | None:
        def convert_name(metric: str) -> str:
            return metric.replace("cache-", "").replace("-", "_")

        if set(metrics_dict.values()) == {0}:
            return None
        return cls(**{convert_name(metric): int(value) for metric, value in metrics_dict.items()})


class AmberfloCustomersClient:
    _METERS = ("cache-write-bytes", "cache-read-bytes", "cache-num-write-blobs", "cache-num-read-blobs")

    @classmethod
    def from_settings(cls, settings) -> AmberfloCustomersClient:
        cfg: AmberFloConfiguration = settings.AMBERFLO_CONFIG
        return cls(env_name=cfg.env_name, api_key=cfg.api_key)

    def __init__(self, env_name: str, api_key: str) -> None:
        self._client = httpx.Client(base_url="https://app.amberflo.io/", headers={"X-API-Key": api_key})
        self._env_name = env_name

    def _get_full_customer_id(self, toolchain_customer_id: str) -> str:
        return f"{self._env_name}_{toolchain_customer_id}"

    def _do_get(self, url: str, api_name: str, params: dict) -> dict:
        try:
            response = self._client.get(url=url, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            error_resp = error.response
            if error_resp.status_code >= 500:
                _logger.warning(f"Failed to to call amberflo API: {api_name}: {error_resp.text[:500]}")
                raise AmberfloTransientError(call_name=api_name, msg=f"HTTP error {error_resp.status_code}")
            raise  # other error HTTP 400- not trainsient, so probably a bug on our side.
        except httpx.RequestError as error:
            raise AmberfloTransientError(call_name=api_name, msg=f"network error: {error!r}")
        return response.json()

    def _do_post(self, url: str, api_name: str, json_payload: dict | list) -> dict:
        try:
            response = self._client.post(url=url, json=json_payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            error_resp = error.response
            if error_resp.status_code >= 500:
                _logger.warning(f"Failed to to call amberflo API: {api_name}: {error_resp.text[:500]}")
                raise AmberfloTransientError(call_name=api_name, msg=f"HTTP error {error_resp.status_code}")
            raise  # other error HTTP 400- not trainsient, so probably a bug on our side.
        except httpx.RequestError as error:
            raise AmberfloTransientError(call_name=api_name, msg=f"network error: {error!r}")
        return response.json()

    def create_customer(self, toolchain_customer_id: str, name: str) -> AmberfloCustomer:
        # https://docs.amberflo.io/docs/create-customers2
        full_customer_id = self._get_full_customer_id(toolchain_customer_id)
        _logger.info(f"create amberflo customer: {full_customer_id=} {name=}")
        payload = {"customerId": full_customer_id, "customerName": name}
        customer_json = self._do_post(url="customer-details", api_name="create_custoemr", json_payload=payload)
        return self.to_customer(customer_json)

    def get_customer(self, toolchain_customer_id: str) -> AmberfloCustomer | None:
        # https://docs.amberflo.io/docs/paging-and-sorting-in-customer-api
        full_customer_id = self._get_full_customer_id(toolchain_customer_id)
        response_json = self._do_get(
            url="customers/paging", api_name="get_customer", params={"sort": "id", "search": full_customer_id}
        )
        items = response_json["items"]
        if len(items) > 1:
            raise ToolchainAssertion(f"More than one customer for id: {full_customer_id} got: {len(items)} items")
        return self.to_customer(items[0]) if items else None

    def to_customer(self, customer_dict: dict) -> AmberfloCustomer:
        update_time = datetime.datetime.fromtimestamp(customer_dict["updateTime"] / 1000, tz=datetime.timezone.utc)
        return AmberfloCustomer(
            customer_id=customer_dict["customerId"], name=customer_dict["customerName"], update_time=update_time
        )

    def get_customer_metrics(
        self, toolchain_customer_id: str, from_day: datetime.date, to_day: datetime.date
    ) -> CustomerMetrics | None:
        # https://docs.amberflo.io/reference/post_usage-batch
        full_customer_id = self._get_full_customer_id(toolchain_customer_id)
        start_timestamp = int(
            datetime.datetime.combine(from_day, datetime.time(), tzinfo=datetime.timezone.utc).timestamp()
        )
        end_timestamp = int(
            datetime.datetime.combine(to_day, datetime.time(), tzinfo=datetime.timezone.utc).timestamp()
        )
        if end_timestamp <= start_timestamp:
            raise ToolchainAssertion(f"Invalid days range {from_day}-{to_day}")
        queries = [self._get_query(meter, full_customer_id, start_timestamp, end_timestamp) for meter in self._METERS]
        resp_json = self._do_post(url="usage/batch", api_name="get_customer_metrics", json_payload=queries)
        metrics_dict = {qr["metadata"]["meterApiName"]: self._get_metrer_data(qr) for qr in resp_json}
        return CustomerMetrics.from_dict(metrics_dict)

    def _get_query(self, metric_name: str, customer_id: str, start_timestamp: int, end_timestamp: int) -> dict:
        # # https://docs.amberflo.io/reference/post_usage
        return {
            "meterApiName": metric_name,
            "aggregation": "SUM",
            "filter": {"customerId": customer_id},
            "timeGroupingInterval": "Day",
            "timeRange": {
                "startTimeInSeconds": start_timestamp,
                "endTimeInSeconds": end_timestamp,
            },
        }

    def _get_metrer_data(self, query_response: dict) -> int:
        meters = query_response["clientMeters"]
        if not meters:
            return 0
        if len(meters) > 1:
            raise ToolchainAssertion("More than on meter value returned.")
        return meters[0]["groupValue"]
