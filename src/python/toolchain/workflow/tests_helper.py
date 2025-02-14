# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import abc

import pytest

from toolchain.workflow.work_dispatcher import WorkDispatcher


@pytest.mark.django_db()
class BaseWorkflowWorkerTests(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def get_dispatcher(self) -> type[WorkDispatcher]:
        pass

    def do_work(self) -> int:
        count = 0
        dispatcher = self.get_dispatcher().for_tests()
        for work_executer in dispatcher._fetch_one_work_batch():
            count += 1
            work_executer.execute()
        return count
