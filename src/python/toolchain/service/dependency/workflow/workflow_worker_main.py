#!/usr/bin/env ./python
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.django.service.workflow.toolchain_workflow_service import ToolchainWorkflowService


def _get_dispatcher():
    # We need to defer loading this module (which imports django models) until after we initialize django (django.setup)
    from toolchain.dependency.workers.dispatcher import DependencyWorkDispatcher

    return DependencyWorkDispatcher


if __name__ == "__main__":
    ToolchainWorkflowService.from_file_name(__file__).run_workflow_server(_get_dispatcher)
