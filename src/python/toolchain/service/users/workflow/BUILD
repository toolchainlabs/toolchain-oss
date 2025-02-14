# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    dependencies=[
        "src/python/toolchain/users",
        "src/python/toolchain/workflow",
    ],
)

pex_binary(
    name="users-worker-manage",
    entry_point="manage.py",
    dependencies=[
        ":workflow",
    ],
)

pex_binary(
    name="users-workflow-worker",
    entry_point="workflow_worker_main.py",
    dependencies=[
        ":workflow",
    ],
)

pex_binary(
    name="users-workflow-maintenance",
    entry_point="workflow_maintenance_main.py",
    dependencies=[
        ":workflow",
    ],
)
