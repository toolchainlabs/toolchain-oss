# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    name="dependency-api",
    dependencies=[
        "src/python/toolchain/dependency",
        "src/python/toolchain/django/webresource",
        "src/python/toolchain/packagerepo/pypi",
        "src/python/toolchain/workflow",
        "src/python/toolchain/django/service/gunicorn",
    ],
)

pex_binary(
    name="dependency-api-manage",
    entry_point="manage.py",
    dependencies=[
        ":dependency-api",
    ],
)

pex_binary(
    name="dependency-api-gunicorn",
    entry_point="gunicorn_main.py",
    dependencies=[
        ":dependency-api",
    ],
)
