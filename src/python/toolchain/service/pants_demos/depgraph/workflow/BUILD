# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    dependencies=[
        "src/python/toolchain/pants_demos/depgraph",
        "src/python/toolchain/workflow",
        "src/python/toolchain/workflow/management/commands",
    ],
)

pex_binary(
    name="pants-demos-depgraph-worker-manage",
    entry_point="manage.py",
    dependencies=[
        ":workflow",
    ],
)

pex_binary(
    name="pants-demos-depgraph-workflow-worker",
    entry_point="workflow_worker_main.py",
    dependencies=[
        ":workflow",
    ],
)

pex_binary(
    name="pants-demos-depgraph-workflow-maintenance",
    entry_point="workflow_maintenance_main.py",
    dependencies=[
        ":workflow",
    ],
)
