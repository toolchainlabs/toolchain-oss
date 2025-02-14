# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).


def test_security_txt(client):
    response = client.get("/.well-known/security.txt")
    assert response.status_code == 200
    assert response["Content-Type"] == "text/plain"
    assert (
        response.content
        == b"\nContact: security@toolchain.com\nExpires: Tue, 14 Oct 2025 10:00 -0700\nPreferred-Languages: en\nCanonical: https://toolchain.com/.well-known/security.txt\nCanonical: https://app.toolchain.com/.well-known/security.txt\n"
    )
