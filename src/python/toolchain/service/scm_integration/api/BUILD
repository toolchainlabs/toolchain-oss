# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    dependencies=[
        "src/python/toolchain/github_integration",
        "src/python/toolchain/github_integration/management/commands",
        "src/python/toolchain/bitbucket_integration",
        "src/python/toolchain/bitbucket_integration/api",
        "src/python/toolchain/workflow",
        "src/python/toolchain/workflow/management/commands",
        "src/python/toolchain/django/service/gunicorn",
    ],
)

pex_binary(
    name="scm-integration-api-manage",
    entry_point="manage.py",
    dependencies=[
        ":api",
    ],
)

pex_binary(
    name="scm-integration-api-gunicorn",
    entry_point="gunicorn_main.py",
    dependencies=[
        ":api",
    ],
)
