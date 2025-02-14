# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    dependencies=[
        ":es_mapping",
    ],
)

resources(name="es_mapping", sources=["run_info_es_mapping.json"])

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
