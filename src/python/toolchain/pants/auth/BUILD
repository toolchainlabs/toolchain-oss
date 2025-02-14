# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    interpreter_constraints=[">=3.7.2,<3.10"],
    resolve="pants-plugin",
    dependencies=[
        ":resources",
    ],
    skip_pyupgrade=True,  # since the rest of the repo is python 3.9 and pyupgrade enforces new syntax
)

resources(name="resources", sources=["favicon.png", "*.html"])

python_tests(
    name="tests",
    resolve="pants-plugin",
    dependencies=[
        "3rdparty/python:pants-plugin-reqs#pytest-responses",
        "!src/python/toolchain/conftest.py:test_utils",
    ],
)

python_test_utils(name="test_utils", resolve="pants-plugin")
