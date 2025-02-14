# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    dependencies=[
        "src/python/toolchain/payments/stripe_integration/management/commands",
        "src/python/toolchain/payments/amberflo_integration/management/commands",
        "src/python/toolchain/workflow/management/commands",
    ]
)


pex_binary(name="payments-api-manage", entry_point="manage.py", dependencies=[":api"])

pex_binary(name="payments-api-gunicorn", entry_point="gunicorn_main.py", dependencies=[":api"])
