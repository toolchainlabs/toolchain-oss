# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    dependencies=[
        "3rdparty/python#social-auth-app-django",
        ":admin-templates",
        ":jinja2-templates",
        ":static",
        "src/python/toolchain/buildsense/ingestion",
        "src/python/toolchain/crawler/base",
        "src/python/toolchain/dependency",
        "src/python/toolchain/django/resources",
        "src/python/toolchain/django/webresource",
        "src/python/toolchain/github_integration",
        "src/python/toolchain/bitbucket_integration",
        "src/python/toolchain/pants_demos/depgraph",
    ],
)

resources(
    name="jinja2-templates",
    sources=["jinja2/**/*"],
)

resources(
    name="admin-templates",
    sources=["templates/**/*"],
)

resources(
    name="static",
    sources=["static/**/*"],
)

python_tests(name="tests")

python_test_utils(name="test_utils")
