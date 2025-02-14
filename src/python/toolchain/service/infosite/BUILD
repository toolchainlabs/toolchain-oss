# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    dependencies=[
        "3rdparty/python#django-csp",  # via MIDDLEWARE
    ],
)

pex_binary(
    name="infosite-manage",
    entry_point="manage.py",
    dependencies=[
        ":infosite",
    ],
)

pex_binary(
    name="infosite-gunicorn",
    entry_point="gunicorn_main.py",
    dependencies=[
        ":infosite",
    ],
)
