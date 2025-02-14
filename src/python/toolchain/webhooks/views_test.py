# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).


def test_robots_txt(client) -> None:
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert response.content == b"User-agent: *\nDisallow: /"


def test_home_page(client) -> None:
    response = client.get("/")
    assert response.status_code == 301
    assert response.url == "https://toolchain.com"
    assert response.get("Location") == "https://toolchain.com"
