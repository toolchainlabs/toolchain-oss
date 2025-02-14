# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    dependencies=[
        "src/python/toolchain/github_integration",
        "src/python/toolchain/github_integration/workers",
        "src/python/toolchain/github_integration/management/commands",
        "src/python/toolchain/workflow/management/commands",
        "src/python/toolchain/workflow",
    ],
)


pex_binary(
    name="scm-integration-worker-manage",
    entry_point="manage.py",
    dependencies=[
        ":workflow",
    ],
)

pex_binary(
    name="scm-integration-workflow-worker",
    entry_point="workflow_worker_main.py",
    dependencies=[
        ":workflow",
    ],
)

pex_binary(
    name="scm-integration-workflow-maintenance",
    entry_point="workflow_maintenance_main.py",
    dependencies=[
        ":workflow",
    ],
)
