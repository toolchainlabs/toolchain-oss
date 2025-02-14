# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json

import pytest

from toolchain.util.config.app_config import AppConfig
from toolchain.util.influxdb.client import InfluxDBConnectionConfig
from toolchain.util.secret.secrets_accessor import DummySecretsAccessor


class TestInfluxDBConnectionConfig:
    @pytest.fixture()
    def secrets_reader(self):
        secrets_accessor = DummySecretsAccessor.create_rotatable()
        secret = {"token": "no-soup-for-you", "org_id": "soup"}
        secrets_accessor.set_secret("influxdb-ovaltine-token", json.dumps(secret))

        return secrets_accessor

    def test_for_local_dev(self, secrets_reader) -> None:
        local = InfluxDBConnectionConfig.for_local_dev(service="ovaltine", secrets_reader=secrets_reader)
        assert local.token == "no-soup-for-you"
        assert local.url == "http://localhost:8086"
        assert local.org_name == "ovaltine"
        assert local.org_id == "soup"

    def test_from_config(self, secrets_reader) -> None:
        app_cfg = AppConfig({"INFLUXDB_CONFIG": {"host": "velvet"}})
        config = InfluxDBConnectionConfig.from_config(service="ovaltine", config=app_cfg, secrets_reader=secrets_reader)
        assert config.token == "no-soup-for-you"
        assert config.url == "http://velvet:80"
        assert config.org_name == "ovaltine"
        assert config.org_id == "soup"
