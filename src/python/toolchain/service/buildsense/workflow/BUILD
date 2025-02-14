# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    dependencies=[
        "src/python/toolchain/buildsense",
        "src/python/toolchain/buildsense/ingestion",
        "src/python/toolchain/workflow",
        "src/python/toolchain/buildsense/management/commands",
    ],
)

pex_binary(
    name="buildsense-worker-manage",
    entry_point="manage.py",
    dependencies=[
        ":workflow",
    ],
)

pex_binary(
    name="buildsense-workflow-worker",
    entry_point="workflow_worker_main.py",
    dependencies=[
        ":workflow",
    ],
)

pex_binary(
    name="buildsense-workflow-maintenance",
    entry_point="workflow_maintenance_main.py",
    dependencies=[
        ":workflow",
    ],
)
