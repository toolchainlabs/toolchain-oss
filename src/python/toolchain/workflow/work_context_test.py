# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.workflow.models import WorkUnit, WorkUnitPayload
from toolchain.workflow.work_context import get_calling_context
from toolchain.workflow.work_executor import WorkExecutor
from toolchain.workflow.worker import Worker


class DummyWorker(Worker):
    """A worker that captures its creator's context, for testing."""

    class Payload(WorkUnitPayload):
        pass

    work_unit_payload_cls = Payload

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context_cls, self.context_work_unit_id = None, None

    def do_work(self, work_unit_payload):
        pass

    def on_success(self, work_unit_payload):
        self.context_cls, self.context_work_unit_id = self._get_context()

    def _get_context(self):
        return self._actually_get_context()

    def _actually_get_context(self):
        return get_calling_context()


class DummyWorkUnit(WorkUnit):
    pass


def test_get_calling_context():
    worker = DummyWorker()
    work_unit = DummyWorkUnit()
    executor = WorkExecutor(work_unit, worker, {})
    executor._execute_completion_func(worker.on_success, work_unit)

    assert DummyWorker == worker.context_cls
    assert work_unit.pk == worker.context_work_unit_id
