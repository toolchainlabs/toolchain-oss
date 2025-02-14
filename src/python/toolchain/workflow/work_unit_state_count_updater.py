# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
import time
from threading import Thread

from toolchain.workflow.config import WorkflowMaintenanceConfig
from toolchain.workflow.models import WorkUnitStateCountDelta

logger = logging.getLogger(__name__)


class WorkUnitStateCountUpdater(Thread):
    """A thread that polls for state count deltas and applies them."""

    def __init__(self, config: WorkflowMaintenanceConfig) -> None:
        super().__init__()
        self.name = "WorkUnitStateCountUpdater"
        self.daemon = True  # So the process exits when the main thread does.
        self._sleep_secs = config.count_update_sleep.total_seconds()
        self._batch_size = config.count_update_batch_size

    def run(self) -> None:
        logger.info(
            f"WorkUnitStateCountUpdater started with id {self.ident} update interval: {self._sleep_secs} seconds."
        )
        while True:
            logger.debug(f"WorkUnitStateCountUpdater going to sleep for {self._sleep_secs} seconds.")
            time.sleep(self._sleep_secs)
            logger.debug("WorkUnitStateCountUpdater woke up.")
            while self.apply_deltas():
                pass

    def apply_deltas(self) -> int:
        try:
            logger.debug(f"WorkUnitStateCountUpdater looking for up to {self._batch_size} deltas to apply.")
            ret = WorkUnitStateCountDelta.apply(self._batch_size)
            logger.debug(f"WorkUnitStateCountUpdater applied {ret} deltas.")
            return ret
        except Exception as e:
            logger.warning(f"Error in state count updater: {e!r}.", exc_info=True)
        return 0
