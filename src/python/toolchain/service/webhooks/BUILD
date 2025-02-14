# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    dependencies=[
        "src/python/toolchain/django/service/gunicorn",
        "src/python/toolchain/webhooks",
    ],
)

pex_binary(
    name="webhooks-manage",
    entry_point="manage.py",
    dependencies=[
        ":webhooks",
    ],
)

pex_binary(
    name="webhooks-gunicorn",
    entry_point="gunicorn_main.py",
    dependencies=[
        ":webhooks",
    ],
)
