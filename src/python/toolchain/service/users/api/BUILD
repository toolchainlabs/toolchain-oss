# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    name="users-api",
    dependencies=[
        "src/python/toolchain/users",
        "src/python/toolchain/users/management/commands",  # add django commands to package
        "src/python/toolchain/django/service/gunicorn",
        "src/python/toolchain/workflow",
        "src/python/toolchain/workflow/management/commands",
    ],
)

pex_binary(
    name="users-api-manage",
    entry_point="manage.py",
    dependencies=[
        ":users-api",
    ],
)

pex_binary(
    name="users-api-gunicorn",
    entry_point="gunicorn_main.py",
    dependencies=[
        ":users-api",
    ],
)
