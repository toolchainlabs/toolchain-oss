# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    dependencies=[
        "3rdparty/python#django-csp",  # via MIDDLEWARE
        "src/python/toolchain/users/jwt",  # using via MIDDLEWARE
        ":service_routes",
        ":static",
        ":templates",
    ],
)

resources(
    name="templates",
    sources=["jinja2/**/*"],
)

resources(
    name="static",
    sources=["static/**/*"],
)
resources(name="service_routes", sources=["service_routes.json"])

files(name="images", sources=["static/servicerouter/images/*.png", "static/servicerouter/images/*.webp"])

python_tests(
    name="tests",
    timeout=120,
    dependencies=[
        "src/python/toolchain/service/buildsense/api",  # For route testing
        "src/python/toolchain/service/dependency/api:dependency-api",  # For route testing
        "src/python/toolchain/service/users/api:users-api",  # For route testing
        "src/python/toolchain/service/users/ui:users-ui",  # For route testing
        "src/python/toolchain/servicerouter",  # Used in `conftest.py`.
        "src/python/toolchain/servicerouter",  # Used in `conftest.py`.
        "src/python/toolchain/users",  # Used in `conftest.py`.
        "src/python/toolchain/buildsense",  # Used in `conftest.py`.
        "src/python/toolchain/buildsense/ingestion",  # Used in `conftest.py`.
    ],
)

python_test_utils(name="test_utils")
