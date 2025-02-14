# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).


def run_workflow_maintenance_forever(django_settings):
    from toolchain.workflow.collector import add_queues_collector
    from toolchain.workflow.work_recovery import WorkRecoverer
    from toolchain.workflow.work_unit_state_count_updater import WorkUnitStateCountUpdater

    config = django_settings.WORKFLOW_MAINTENANCE_CONFIG
    WorkUnitStateCountUpdater(config).start()
    add_queues_collector()
    WorkRecoverer.run_recover_forever(config)
