# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    dependencies=[
        ":templates",
        ":static",
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
