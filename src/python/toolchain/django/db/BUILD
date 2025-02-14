# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    dependencies=[
        "3rdparty/python:psycopg2",  # Via Django's DB Engine.
    ],
)

python_tests(
    name="tests",
    dependencies=[
        "src/python/toolchain/django/db/testapp",
    ],
)

python_test_utils(name="test_utils")
