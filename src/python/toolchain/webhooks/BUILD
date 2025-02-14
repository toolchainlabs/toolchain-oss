# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    dependencies=[
        ":certs",
        ":descriptors",
    ],
)

python_tests(name="tests")

resources(
    name="certs",
    sources=["*.pem"],
)

resources(name="descriptors", sources=["descriptors/*.json"])

python_test_utils(name="test_utils")
