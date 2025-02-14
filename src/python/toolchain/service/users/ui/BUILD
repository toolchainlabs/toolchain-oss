# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    name="users-ui",
    dependencies=[
        "3rdparty/python#django-csp",  # via MIDDLEWARE
        "3rdparty/python#social-auth-app-django",
        "src/python/toolchain/django/service/gunicorn",
        "src/python/toolchain/users",
        "src/python/toolchain/users/ui",
        "src/python/toolchain/workflow",
    ],
)

pex_binary(
    name="users-ui-manage",
    entry_point="manage.py",
    dependencies=[
        "src/python/toolchain/users/management/commands",  # Include commands
        ":users-ui",
    ],
)

pex_binary(
    name="users-ui-gunicorn",
    entry_point="gunicorn_main.py",
    dependencies=[
        ":users-ui",
    ],
)
