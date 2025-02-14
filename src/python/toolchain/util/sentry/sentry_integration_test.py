# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.constants import ToolchainServiceInfo
from toolchain.util.sentry.sentry_integration import SentryEventsFilter, init_sentry_for_django


def test_init() -> None:
    cfg = {"TOOLCHAIN_SERVICE_TYPE": "web-ui"}
    service_info = ToolchainServiceInfo.from_config(service_name="aluminum", config=cfg)
    client = init_sentry_for_django(
        dsn="http://fakekey@fake.com/888888",
        environment="testing",
        service_info=service_info,
        events_filter=SentryEventsFilter(),
    )._client
    assert client.dsn == "http://fakekey@fake.com/888888"
    assert client.options["send_default_pii"] is True
    assert client.options["release"] is None
    assert client.options["environment"] == "testing"


def test_no_init() -> None:
    cfg = {"TOOLCHAIN_SERVICE_TYPE": "web-ui"}
    service_info = ToolchainServiceInfo.from_config(service_name="aluminum", config=cfg)
    assert (
        init_sentry_for_django(
            dsn="", environment="testing", service_info=service_info, events_filter=SentryEventsFilter()
        )
        is None
    )
