# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    dependencies=[
        "3rdparty/python#django-csp",  # via MIDDLEWARE
        "src/python/toolchain/django/service/gunicorn",
        "src/python/toolchain/pants_demos/depgraph",
        "src/python/toolchain/django/postgres_setrole",
        "src/python/toolchain/workflow",
        "src/python/toolchain/workflow/management/commands",
    ],
)


pex_binary(
    name="pants-demos-depgraph-web-manage",
    entry_point="manage.py",
    dependencies=[
        ":web",
    ],
)

pex_binary(
    name="pants-demos-depgraph-web-gunicorn",
    entry_point="gunicorn_main.py",
    dependencies=[
        ":web",
    ],
)
