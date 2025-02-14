# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Note that we require the sources= stanzas here, because they recursive-glob,
# while the default does not.

python_sources(
    dependencies=[
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

python_tests(name="tests")

pex_binary(name="lockfile_to_urls", entry_point="lockfile_to_urls.py")

python_test_utils(name="test_utils")
