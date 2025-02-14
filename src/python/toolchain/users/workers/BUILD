# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    dependencies=[
        ":email_templates",
    ]
)

python_tests(name="tests")

python_test_utils(name="test_utils")

resources(
    name="email_templates",
    sources=["email_templates/*.html"],
)
