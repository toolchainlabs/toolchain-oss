# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_sources()


pex_binary(name="notifications-worker-manage", entry_point="manage.py", dependencies=[":workflow"])

pex_binary(name="notifications-workflow-worker", entry_point="workflow_worker_main.py", dependencies=[":workflow"])

pex_binary(
    name="notifications-workflow-maintenance", entry_point="workflow_maintenance_main.py", dependencies=[":workflow"]
)
