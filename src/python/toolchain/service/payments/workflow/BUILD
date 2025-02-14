# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    dependencies=[
        "src/python/toolchain/payments/stripe_integration/management/commands",
        "src/python/toolchain/payments/amberflo_integration/management/commands",
        "src/python/toolchain/workflow/management/commands",
    ]
)


pex_binary(name="payments-worker-manage", entry_point="manage.py", dependencies=[":workflow"])

pex_binary(name="payments-workflow-worker", entry_point="workflow_worker_main.py", dependencies=[":workflow"])

pex_binary(name="payments-workflow-maintenance", entry_point="workflow_maintenance_main.py", dependencies=[":workflow"])
