# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources(
    dependencies=[
        "src/python/toolchain/crawler/base",
        "src/python/toolchain/crawler/pypi",
        "src/python/toolchain/crawler/pypi/management/commands",  # So commands are available to manage.py.
        "src/python/toolchain/packagerepo/pypi",
        "src/python/toolchain/workflow",
        "src/python/toolchain/workflow/management/commands",  # So commands are available to manage.py.
    ],
)

pex_binary(
    name="crawler-pypi-worker-manage",
    entry_point="manage.py",
    dependencies=[
        ":workflow",
    ],
)

pex_binary(
    name="crawler-pypi-workflow-worker",
    entry_point="workflow_worker_main.py",
    dependencies=[
        ":workflow",
    ],
)

pex_binary(
    name="crawler-pypi-workflow-maintenance",
    entry_point="workflow_maintenance_main.py",
    dependencies=[
        ":workflow",
    ],
)
