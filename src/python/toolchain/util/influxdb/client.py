# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
from dataclasses import dataclass

from influxdb_client import InfluxDBClient, Organization

from toolchain.util.config.app_config import AppConfig

LOCAL_ADMIN_URL = "http://localhost:8086"


@dataclass(frozen=True)
class InfluxDBConnectionConfig:
    LOCAL_DEV_PORT = 8086

    org_name: str  # Each service that uses the DB (buildsense, github-integration, etc... has its own org in influxdb terms)
    host: str
    port: int
    token: str | None = None
    org_id: str | None = None

    @classmethod
    def get_secret_name(cls, service: str, is_read_only: bool) -> str:
        return f"influxdb-{service}-ro-token" if is_read_only else f"influxdb-{service}-token"

    @classmethod
    def for_local_dev(cls, service: str, secrets_reader, is_read_only: bool = False) -> InfluxDBConnectionConfig:
        influx_secret = secrets_reader.get_json_secret_or_raise(cls.get_secret_name(service, is_read_only))
        return cls(org_name=service, host="localhost", port=cls.LOCAL_DEV_PORT, **influx_secret)

    @classmethod
    def from_config(
        cls, service: str, config: AppConfig, secrets_reader, is_read_only: bool = False
    ) -> InfluxDBConnectionConfig:
        # When running in k8s
        db_config: dict[str, str] = config.get_config_section("INFLUXDB_CONFIG")
        influx_secret = secrets_reader.get_json_secret_or_raise(cls.get_secret_name(service, is_read_only))
        return cls(org_name=service, host=db_config["host"], port=80, **influx_secret)

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


def get_client(config: InfluxDBConnectionConfig, request_timeout: datetime.timedelta | None = None) -> InfluxDBClient:
    request_timeout_msec = 1000 * (request_timeout.total_seconds() if request_timeout else 10)
    return InfluxDBClient(url=config.url, token=config.token, org=config.org_name, timeout=int(request_timeout_msec))


def get_client_for_admin(token: str) -> InfluxDBClient:
    return InfluxDBClient(url=LOCAL_ADMIN_URL, token=token)


def get_org(client: InfluxDBClient, org_name: str) -> Organization | None:
    for org in client.organizations_api().find_organizations():
        if org.name == org_name:
            return org
    return None
