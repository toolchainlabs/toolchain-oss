# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources()


python_tests(
    name="tests",
    dependencies=[
        ":fixtures",
    ],
)


resources(
    name="fixtures",
    sources=["fixtures/*.json"],
)

python_test_utils(name="test_utils")
