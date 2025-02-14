# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    dependencies=[
        "src/python/toolchain/dependency",
        "src/python/toolchain/dependency/management/commands",  # Include commands
        "src/python/toolchain/workflow",
    ],
)

pex_binary(
    name="dependency-worker-manage",
    entry_point="manage.py",
    dependencies=[
        ":workflow",
    ],
)

pex_binary(
    name="dependency-workflow-worker",
    entry_point="workflow_worker_main.py",
    dependencies=[
        ":workflow",
    ],
)

pex_binary(
    name="dependency-workflow-maintenance",
    entry_point="workflow_maintenance_main.py",
    dependencies=[
        ":workflow",
    ],
)
