# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.test import Client


def test_check_sentry():
    response = Client(raise_request_exception=False).get("/checksz/sentryz")
    assert response.status_code == 500
    assert response.content == (
        b"\n<!doctype html>"
        + b'\n<html lang="en">\n<head>\n  <title>Server Error (500)</title>\n</head>\n'
        + b"<body>\n  <h1>Server Error (500)</h1><p></p>\n</body>\n"
        + b"</html>\n"
    )
