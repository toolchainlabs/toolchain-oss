# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    dependencies=[
        ":static",
        ":templates",
        ":txt",
        ":team",
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

resources(
    name="txt",
    sources=["*.txt"],
)

resource(name="team", source="team.json")

python_tests(name="tests")

python_test_utils(name="test_utils")
