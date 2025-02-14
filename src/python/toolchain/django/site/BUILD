# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    dependencies=[
        "3rdparty/python#django-extensions",  # Via INSTALLED_APPS.
        "3rdparty/python:psycopg2",  # Via Django's DB Engine.
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

python_tests(name="tests")

python_test_utils(name="test_utils")
