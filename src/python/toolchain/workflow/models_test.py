# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime

import pytest
from django.db.models import CharField

from toolchain.base.datetime_tools import utcnow
from toolchain.django.db.transaction_broker import TransactionBroker
from toolchain.workflow.models import WorkUnit, WorkUnitPayload

transaction = TransactionBroker("workflow")


class TopLevelWork(WorkUnitPayload):
    value = CharField(max_length=20)


class RequiredWork(WorkUnitPayload):
    value = CharField(max_length=20)


@pytest.mark.django_db(transaction=True)
class TestWorkUnitModel:
    def _do_work_with_error(self, work_unit):
        now = utcnow()
        work_unit.take_lease(until=now + datetime.timedelta(seconds=10), last_attempt=now, node="soup")
        work_unit.refresh_from_db()
        with transaction.atomic():
            work_unit.permanent_error_occurred()

    def _do_work_with_success(self, work_unit, rerun_requirers=True):
        now = utcnow()
        work_unit.take_lease(until=now + datetime.timedelta(seconds=10), last_attempt=now, node="soup")
        work_unit.refresh_from_db()
        with transaction.atomic():
            work_unit.work_succeeded(rerun_requirers)

    def test_permanent_error_occurred(self):
        top = TopLevelWork.objects.create(value="top1")
        self._do_work_with_error(top.work_unit)
        assert WorkUnit.objects.get(id=top.work_unit_id).state == WorkUnit.INFEASIBLE

    def test_permanent_error_propagation(self):
        with transaction.atomic():
            top = TopLevelWork.objects.create(value="top1")
            sub1 = RequiredWork.objects.create(value="sub1")
            top.add_requirement_by_id(sub1.work_unit_id)

        self._do_work_with_error(sub1.work_unit)

        assert WorkUnit.objects.get(id=sub1.work_unit_id).state == WorkUnit.INFEASIBLE
        top_wu = WorkUnit.objects.get(id=top.work_unit_id)
        assert top_wu.state == WorkUnit.INFEASIBLE
        assert top_wu.num_unsatisfied_requirements == 1

    def test_mark_as_feasible_for_ids_invalid_id(self):
        assert WorkUnit.mark_as_feasible_for_ids({10, 30, 99}) == tuple()

    def test_mark_as_feasible_for_ids_some_invalid_ids(self):
        top1 = TopLevelWork.objects.create(value="top1")
        top2 = TopLevelWork.objects.create(value="top2")
        top3 = TopLevelWork.objects.create(value="top3")
        top4 = TopLevelWork.objects.create(value="top4")
        top5 = TopLevelWork.objects.create(value="top5")
        self._do_work_with_error(top1.work_unit)
        self._do_work_with_error(top2.work_unit)
        self._do_work_with_error(top3.work_unit)
        self._do_work_with_error(top4.work_unit)
        self._do_work_with_success(top5.work_unit)

        work_units = WorkUnit.mark_as_feasible_for_ids({top1.work_unit_id, top5.work_unit_id, top1.work_unit_id + 300})
        assert (top1.work_unit,) == work_units
        assert WorkUnit.objects.get(id=top1.work_unit_id).state == WorkUnit.READY
        assert WorkUnit.objects.get(id=top2.work_unit_id).state == WorkUnit.INFEASIBLE
        assert WorkUnit.objects.get(id=top5.work_unit_id).state == WorkUnit.SUCCEEDED

    def test_mark_as_feasible_for_ids_multiple(self):
        top1 = TopLevelWork.objects.create(value="top1")
        top2 = TopLevelWork.objects.create(value="top2")
        top3 = TopLevelWork.objects.create(value="top3")
        top4 = TopLevelWork.objects.create(value="top4")
        top5 = TopLevelWork.objects.create(value="top5")
        self._do_work_with_error(top1.work_unit)
        self._do_work_with_error(top2.work_unit)
        self._do_work_with_error(top3.work_unit)
        self._do_work_with_error(top4.work_unit)

        work_units = WorkUnit.mark_as_feasible_for_ids({top2.work_unit_id, top5.work_unit_id, top4.work_unit_id})
        assert len(work_units) == 2
        assert set(work_units) == {top2.work_unit, top4.work_unit}
        assert WorkUnit.objects.get(id=top1.work_unit_id).state == WorkUnit.INFEASIBLE
        assert WorkUnit.objects.get(id=top2.work_unit_id).state == WorkUnit.READY
        assert WorkUnit.objects.get(id=top3.work_unit_id).state == WorkUnit.INFEASIBLE
        assert WorkUnit.objects.get(id=top4.work_unit_id).state == WorkUnit.READY

    def test_mark_as_feasible_propagation_single_failure(self):
        with transaction.atomic():
            top = TopLevelWork.objects.create(value="top1")
            sub1 = RequiredWork.objects.create(value="sub1")
            sub2 = RequiredWork.objects.create(value="sub2")
            sub3 = RequiredWork.objects.create(value="sub3")
            top.add_requirement_by_id(sub1.work_unit_id)
            top.add_requirement_by_id(sub2.work_unit_id)
            top.add_requirement_by_id(sub3.work_unit_id)

        assert WorkUnit.objects.get(id=top.work_unit_id).num_unsatisfied_requirements == 3
        self._do_work_with_error(sub1.work_unit)
        assert WorkUnit.objects.get(id=top.work_unit_id).num_unsatisfied_requirements == 3
        self._do_work_with_success(sub2.work_unit)
        assert WorkUnit.objects.get(id=top.work_unit_id).num_unsatisfied_requirements == 2
        self._do_work_with_success(sub3.work_unit)
        assert WorkUnit.objects.get(id=top.work_unit_id).num_unsatisfied_requirements == 1

        WorkUnit.mark_as_feasible_for_ids({sub1.work_unit_id})
        sub1_wu = WorkUnit.objects.get(id=sub1.work_unit_id)
        assert sub1_wu.state == WorkUnit.READY
        top_wu = WorkUnit.objects.get(id=top.work_unit_id)
        assert top_wu.state == WorkUnit.INFEASIBLE
        assert top_wu.num_unsatisfied_requirements == 1

        self._do_work_with_success(sub1_wu)
        assert WorkUnit.objects.get(id=sub1.work_unit_id).state == WorkUnit.SUCCEEDED
        top_wu = WorkUnit.objects.get(id=top.work_unit_id)
        assert top_wu.state == WorkUnit.READY
        assert top_wu.num_unsatisfied_requirements == 0

    def test_mark_as_feasible_propagation_multiple_failures(self):
        with transaction.atomic():
            top = TopLevelWork.objects.create(value="top1")
            sub1 = RequiredWork.objects.create(value="sub1")
            sub2 = RequiredWork.objects.create(value="sub2")
            sub3 = RequiredWork.objects.create(value="sub3")
            top.add_requirement_by_id(sub1.work_unit_id)
            top.add_requirement_by_id(sub2.work_unit_id)
            top.add_requirement_by_id(sub3.work_unit_id)

        assert WorkUnit.objects.get(id=top.work_unit_id).num_unsatisfied_requirements == 3
        self._do_work_with_error(sub1.work_unit)
        assert WorkUnit.objects.get(id=top.work_unit_id).num_unsatisfied_requirements == 3
        self._do_work_with_success(sub2.work_unit)
        assert WorkUnit.objects.get(id=top.work_unit_id).num_unsatisfied_requirements == 2
        self._do_work_with_error(sub3.work_unit)
        assert WorkUnit.objects.get(id=top.work_unit_id).num_unsatisfied_requirements == 2

        WorkUnit.mark_as_feasible_for_ids({sub1.work_unit_id})
        assert WorkUnit.objects.get(id=sub1.work_unit_id).state == WorkUnit.READY
        top_wu = WorkUnit.objects.get(id=top.work_unit_id)
        assert top_wu.state == WorkUnit.INFEASIBLE
        assert top_wu.num_unsatisfied_requirements == 2

        self._do_work_with_success(WorkUnit.objects.get(id=sub1.work_unit_id))
        assert WorkUnit.objects.get(id=sub1.work_unit_id).state == WorkUnit.SUCCEEDED
        top_wu = WorkUnit.objects.get(id=top.work_unit_id)
        assert top_wu.state == WorkUnit.INFEASIBLE
        assert top_wu.num_unsatisfied_requirements == 1

        WorkUnit.mark_as_feasible_for_ids({sub3.work_unit_id})

        top_wu = WorkUnit.objects.get(id=top.work_unit_id)
        assert top_wu.state == WorkUnit.INFEASIBLE
        assert top_wu.num_unsatisfied_requirements == 1

        self._do_work_with_success(WorkUnit.objects.get(id=sub3.work_unit_id))
        top_wu = WorkUnit.objects.get(id=top.work_unit_id)
        assert top_wu.state == WorkUnit.READY
        assert top_wu.num_unsatisfied_requirements == 0
