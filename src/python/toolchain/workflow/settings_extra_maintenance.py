# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.django.site.settings.service import config
from toolchain.workflow.config import WorkflowMaintenanceConfig
from toolchain.workflow.settings_worker_common import *  # noqa: F403, F401

# Extra settings to import into the settings.py of workflow maintenance services.
WORKFLOW_MAINTENANCE_CONFIG = WorkflowMaintenanceConfig.from_config(config)
