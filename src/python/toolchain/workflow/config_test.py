# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime

from toolchain.util.config.app_config import AppConfig
from toolchain.workflow.config import WorkflowMaintenanceConfig, WorkflowWorkerConfig
from toolchain.workflow.worker import Worker


class TestWorkflowMaintenanceConfig:
    def test_defaults(self) -> None:
        config = WorkflowMaintenanceConfig.from_config(AppConfig({}))
        assert config.recovery_batch_size == 1000
        assert config.recovery_sleep == datetime.timedelta(seconds=5)
        assert config.count_update_batch_size == 10000
        assert config.count_update_sleep == datetime.timedelta(seconds=1)

    def test_default_values(self) -> None:
        config = WorkflowMaintenanceConfig.from_config(AppConfig({}))
        assert config.recovery_batch_size == 1000
        assert config.recovery_sleep == datetime.timedelta(seconds=5)
        assert config.count_update_batch_size == 10000
        assert config.count_update_sleep == datetime.timedelta(seconds=1)

    def test_values(self):
        config = WorkflowMaintenanceConfig.from_config(
            AppConfig(
                {
                    "WORKFLOW_MAINTENANCE": {
                        "recovery": {"batch_size": 331, "sleep_secs": 81},
                        "count_update": {"batch_size": 93, "sleep_secs": 29},
                    }
                }
            )
        )
        assert config.recovery_batch_size == 331
        assert config.recovery_sleep == datetime.timedelta(seconds=81)
        assert config.count_update_batch_size == 93
        assert config.count_update_sleep == datetime.timedelta(seconds=29)


class PizzaWorker(Worker):
    pass


class BagelsWorker(Worker):
    pass


class SubmarineWorker(Worker):
    pass


class MuffinWorker(Worker):
    pass


class TestWorkflowWorkerConfig:
    def test_defaults(self) -> None:
        config = WorkflowWorkerConfig.from_config(AppConfig({}))
        assert config.batch_size == 1
        assert config.num_executor_threads == 1
        assert config.worker_classes_names == tuple()

    def test_default_values(self) -> None:
        config = WorkflowWorkerConfig.from_config(AppConfig({}))
        assert config.batch_size == 1
        assert config.num_executor_threads == 1
        assert config.worker_classes_names == tuple()

    def test_values(self) -> None:
        config = WorkflowWorkerConfig.from_config(
            AppConfig({"WORKFLOW": {"class_names": ["tinsel"], "batch_size": 83, "num_executor_threads": 12}})
        )
        assert config.batch_size == 83
        assert config.num_executor_threads == 12
        assert config.worker_classes_names == ("tinsel",)

    def test_extrapolate_worker_classes_default(self) -> None:
        workers = (BagelsWorker, SubmarineWorker, MuffinWorker)
        config = WorkflowWorkerConfig.from_config(AppConfig({}))
        assert config.extrapolate_worker_classes(workers) == (BagelsWorker, SubmarineWorker, MuffinWorker)

    def test_extrapolate_worker_classes_single(self) -> None:
        workers = (PizzaWorker, BagelsWorker, SubmarineWorker, MuffinWorker)
        config = WorkflowWorkerConfig.from_config(AppConfig({"WORKFLOW": {"class_names": ["PizzaWorker"]}}))
        assert config.extrapolate_worker_classes(workers) == (PizzaWorker,)

    def test_extrapolate_worker_classes_multiple(self) -> None:
        workers = (PizzaWorker, BagelsWorker, SubmarineWorker, MuffinWorker)
        config = WorkflowWorkerConfig.from_config(
            AppConfig({"WORKFLOW": {"class_names": ["MuffinWorker", "BagelsWorker"]}})
        )
        assert config.extrapolate_worker_classes(workers) == (MuffinWorker, BagelsWorker)

    def test_extrapolate_worker_classes_exclude(self) -> None:
        workers = (PizzaWorker, BagelsWorker, SubmarineWorker, MuffinWorker)
        config = WorkflowWorkerConfig.from_config(AppConfig({"WORKFLOW": {"class_names": ["-SubmarineWorker"]}}))
        assert config.extrapolate_worker_classes(workers) == (PizzaWorker, BagelsWorker, MuffinWorker)
