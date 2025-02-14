# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Note that we require the sources= stanzas here, because they recursive-glob,
# while the default does not.

python_sources(
    dependencies=[
        ":templates",
        "src/python/toolchain/crawler/maven/migrations",  # So we can run migrations where this service is deployed
    ],
)

resources(
    name="templates",
    sources=["jinja2/**/*"],
    dependencies=[
        "src/python/toolchain/django/site:templates",
    ],
)
