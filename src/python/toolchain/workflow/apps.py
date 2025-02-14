# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.apps import AppConfig

from toolchain.workflow.django_signals import register_signals_for_workexceptionlogs


class WorkflowAppConfig(AppConfig):
    name = "toolchain.workflow"
    label = "workflow"
    verbose_name = "Workflow System"

    def ready(self):
        register_signals_for_workexceptionlogs()
