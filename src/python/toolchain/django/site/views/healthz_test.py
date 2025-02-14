# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.content == b"OK"
