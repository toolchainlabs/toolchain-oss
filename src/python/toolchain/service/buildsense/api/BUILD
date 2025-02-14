# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    dependencies=[
        "src/python/toolchain/buildsense",  # via settings.py.
        "src/python/toolchain/buildsense/ingestion",  # via settings.py.
        "src/python/toolchain/buildsense/management/commands",
        "src/python/toolchain/django/service/gunicorn",
        "src/python/toolchain/workflow",
        "src/python/toolchain/workflow/management/commands",
    ],
)

pex_binary(
    name="buildsense-api-manage",
    entry_point="manage.py",
    dependencies=[
        ":api",
    ],
)

pex_binary(
    name="buildsense-api-gunicorn",
    entry_point="gunicorn_main.py",
    dependencies=[
        ":api",
    ],
)
