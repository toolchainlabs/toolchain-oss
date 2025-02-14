# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    name="maven",
    dependencies=[
        ":static",
        ":templates",
    ],
)

resources(
    name="templates",
    sources=["jinja2/**/*"],
    dependencies=[
        "src/python/toolchain/django/site:templates",
    ],
)

resources(
    name="static",
    sources=["static/**/*"],
)

python_tests(name="tests")

python_test_utils(name="test_utils")
