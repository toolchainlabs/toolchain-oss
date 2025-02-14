# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass

from toolchain.util.config.app_config import AppConfig

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkflowMaintenanceConfig:
    recovery_batch_size: int
    recovery_sleep: datetime.timedelta
    count_update_batch_size: int
    count_update_sleep: datetime.timedelta

    @classmethod
    def from_config(cls, config: AppConfig) -> WorkflowMaintenanceConfig:
        workflow_cfg = config.get_config_section("WORKFLOW_MAINTENANCE")
        recovery_cfg = workflow_cfg.get("recovery", {"batch_size": 1000, "sleep_secs": 5})  # type: ignore[union-attr]
        count_update_cfg = workflow_cfg.get("count_update", {"batch_size": 10000, "sleep_secs": 1})  # type: ignore[union-attr]
        return cls(
            recovery_batch_size=recovery_cfg["batch_size"],
            recovery_sleep=datetime.timedelta(seconds=recovery_cfg["sleep_secs"]),
            count_update_batch_size=count_update_cfg["batch_size"],
            count_update_sleep=datetime.timedelta(seconds=count_update_cfg["sleep_secs"]),
        )


@dataclass(frozen=True)
class WorkflowWorkerConfig:
    worker_classes_names: tuple[str, ...]
    batch_size: int
    num_executor_threads: int
    worker_calls_log_level: int

    @classmethod
    def from_config(cls, config: AppConfig) -> WorkflowWorkerConfig:
        workflow_cfg = config.get_config_section("WORKFLOW")
        class_names = tuple(workflow_cfg.get("class_names", []))  # type: ignore[union-attr]
        return cls(
            worker_classes_names=class_names,
            batch_size=workflow_cfg.get("batch_size", 1),  # type: ignore[union-attr]
            num_executor_threads=workflow_cfg.get("num_executor_threads", 1),  # type: ignore[union-attr]
            worker_calls_log_level=workflow_cfg.get("worker_calls_log_level", logging.INFO),
        )

    def extrapolate_worker_classes(self, all_worker_classes: tuple[type, ...]) -> tuple[type, ...]:
        worker_classes_names = self.worker_classes_names
        if not worker_classes_names:
            return all_worker_classes
        all_worker_classes_by_name = {cls.__name__: cls for cls in all_worker_classes}

        worker_classes = []
        for prefixed_cls_name in worker_classes_names:
            if prefixed_cls_name.startswith("-"):
                cls_name = prefixed_cls_name[1:]
                worker_classes.extend(
                    [worker_cls for name, worker_cls in all_worker_classes_by_name.items() if name != cls_name]
                )
            else:
                worker_classes.append(all_worker_classes_by_name[prefixed_cls_name])
        return tuple(worker_classes) or all_worker_classes
