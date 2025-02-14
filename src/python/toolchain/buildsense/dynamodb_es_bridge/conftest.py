# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest


@pytest.fixture(autouse=True)
def _disable_real_aws(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "fake-aws-creds-key-id")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-aws-creds-access-key")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "fake-aws-creds-session-token")
