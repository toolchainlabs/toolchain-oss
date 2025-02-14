# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    dependencies=[
        ":email_templates",
    ],
)

python_tests(name="tests")

python_test_utils(name="test_utils", dependencies=["src/python/toolchain/django/site"])


resources(
    name="email_templates",
    sources=["email_templates/*.html"],
)
