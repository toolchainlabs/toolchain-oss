# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    dependencies=[
        "src/python/toolchain/django/service/gunicorn",
        "src/python/toolchain/servicerouter",
        "src/python/toolchain/workflow",  # Used in servicerouter:settings, users_db_router. See #10115
        "src/python/toolchain/users",  # Used in servicerouter:settings, users_db_router. See #10115
    ],
)

pex_binary(
    name="servicerouter-manage",
    entry_point="manage.py",
    dependencies=[
        ":servicerouter",
    ],
)

pex_binary(
    name="servicerouter-gunicorn",
    entry_point="gunicorn_main.py",
    dependencies=[
        ":servicerouter",
    ],
)
