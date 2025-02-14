#!/usr/bin/env ./python
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.django.service.workflow.toolchain_workflow_service import ToolchainWorkflowService

if __name__ == "__main__":
    ToolchainWorkflowService.from_file_name(__file__, "settings_maintenance").run_workflow_maintenance()
