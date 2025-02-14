# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
import random
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property

from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import Error as DbError
from django.db.models import (
    CASCADE,
    AutoField,
    BigAutoField,
    CharField,
    Count,
    DateTimeField,
    F,
    ForeignKey,
    Index,
    IntegerField,
    Manager,
    ManyToManyField,
    OneToOneField,
    QuerySet,
    Sum,
    TextField,
    Value,
)
from prometheus_client import Counter

from toolchain.base.contexttimer import Timer
from toolchain.base.datetime_tools import UNIX_EPOCH, utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.db.base_models import ToolchainModel
from toolchain.django.db.transaction_broker import TransactionBroker
from toolchain.workflow.constants import WorkExceptionCategory
from toolchain.workflow.error import WorkException
from toolchain.workflow.work_context import get_calling_context

logger = logging.getLogger(__name__)


transaction = TransactionBroker("workflow")


WORKUNIT_STATE_TRANSITION = Counter(
    name="toolchain_workflow_workunit_state_transition",
    documentation="Count work unit state transition labelled by work unit payload type & work unit state.",
    labelnames=["payload_model", "payload_app", "current_state", "new_state"],
)


class WorkUnit(ToolchainModel):
    """The execution state of a work unit."""

    class Meta:
        indexes = [Index(fields=["state", "payload_ctype"]), GinIndex(fields=["search_vector"])]

    class UnexpectedState(ToolchainAssertion):
        def __init__(self, work_unit: WorkUnit) -> None:
            super().__init__(f"Unexpected state {work_unit.state} for work unit {work_unit}")

    # Work state.
    PENDING = "PEN"  # This work has unsatisfied requirements.
    READY = "REA"  # This work has no unsatisfied requirements, and can be leased by an available worker.
    LEASED = "LEA"  # This work is currently leased by some worker.
    SUCCEEDED = "SUC"  # This work has completed successfully.
    INFEASIBLE = "INF"  # A worker encountered a permanent error while performing this work.

    STATE_CHOICES = (
        (PENDING, "pending"),
        (READY, "ready"),
        (LEASED, "leased"),
        (SUCCEEDED, "succeeded"),
        (INFEASIBLE, "infeasible"),
    )

    state_to_str = {x[0]: x[1] for x in STATE_CHOICES}

    id = BigAutoField(primary_key=True)

    payload_ctype = ForeignKey(ContentType, on_delete=CASCADE, db_index=True, editable=False)

    # The state this work unit is in.
    state = CharField(max_length=3, choices=STATE_CHOICES, default=READY)

    # Other work that must be completed before this work can be attempted.
    requirements = ManyToManyField(
        "self", symmetrical=False, through="WorkUnitRequirement", related_name="required_by", blank=True
    )

    # Denormalized count of self.requirements.all(), for performance.
    # A PENDING workunit must have num_unsatisfied_requirements > 0.
    # A READY, LEASED or SUCCEEDED workunit must have num_unsatisfied_requirements == 0.
    # An INFEASIBLE workunit may have any num_unsatisfied_requirements >= 0.
    num_unsatisfied_requirements = IntegerField(default=0)

    # The WorkUnit that caused this one to be created, if any.
    # Deduced automatically if the creation is via save(), in a WorkExecutor on_* callback.
    # Must be set explicitly if using bulk-create, or creating outside a WorkExecutor callback.
    creator = ForeignKey("self", on_delete=CASCADE, related_name="created", null=True)

    # When this work was created.
    created_at = DateTimeField(default=UNIX_EPOCH, db_index=True, editable=False)

    # The last time a worker leased this work unit.
    last_attempt = DateTimeField(default=UNIX_EPOCH, db_index=True)

    # When this work was executed successfully.
    succeeded_at = DateTimeField(default=UNIX_EPOCH, db_index=True)

    # When the most recent lease on this work unit will expire (or has expired).
    # Set when a worker acquires a lease, or when this work unit is rescheduled by a worker
    # to be retried in the future.
    # None if no worker has held a lease on this work unit since its last
    # successful completion.
    leased_until = DateTimeField(null=True, default=None, db_index=True)

    # A 36-byte uuid string (e.g., 'd3fa24dc-8a6a-11e6-8605-040ccee06e78') identifying
    # the worker that holds (or held) the most recent lease on this work unit.
    # An empty string if no worker holds a lease on this work unit.  Note that in this case
    # leased_until may still be non-null, if the work has been rescheduled.
    lease_holder = CharField(max_length=36, blank=True, default="", db_index=True)

    # Identifies the node currently executing this workunit, if any.
    # The meaning of "node" (machine, container, process, thread etc.), and the interpretation of this field,
    # are unspecified.  This field is optional; The workflow system  doesn't require it in order to function.
    # It's primarily used to provide information to admins when examining the state of a running workflow system.
    node = CharField(max_length=100, blank=True, default="", db_index=True)

    # A useful human-readable description of this WorkUnit.
    description = CharField(max_length=1024)

    # Index of the description and other strings useful when searching for work units in the admin console.
    search_vector = SearchVectorField(null=True)

    @classmethod
    def locked(cls, pk: int) -> WorkUnit:
        return cls.objects.filter(pk=pk).select_for_update().get()

    @classmethod
    def _lock_table(cls, transaction) -> None:
        cursor = transaction.connection.cursor()
        logger.debug("Locking WorkUnit table...")
        cursor.execute(f"LOCK TABLE {cls._meta.db_table} IN EXCLUSIVE MODE")
        logger.debug("WorkUnit table locked!")

    @cached_property
    def payload(self):
        return self.payload_ctype.model_class().objects.filter(work_unit=self).get()

    def state_str(self) -> str | None:
        return self.state_to_str.get(self.state)

    # State transitions.
    #
    # IMPORTANT:  For all these state transition methods,
    #   - Always call them in a transaction, while holding a row lock on the instance.
    #   - Remember to call save() on the instance.
    #
    # Note that some of these methods can cause deadlocks in rare circumstances. The work executor will
    # detect these and ensure that any rolled-back work will be retried.

    def add_requirement(self, target_pk: int) -> bool:
        # Requirements can be added when the work unit is created,
        # and workers can add them when attempting the work.
        self._assert_state([WorkUnit.PENDING, WorkUnit.READY, WorkUnit.LEASED])

        if self.pk is None:
            raise ToolchainAssertion(f"WorkUnit must be saved to the db before creating a requirement on it: {self}")
        _, created = WorkUnitRequirement.objects.get_or_create(source=self, target_id=target_pk)
        if created:
            # Lock the target if it's not SUCCEEDED, so it won't become SUCCEEDED while we're updating our
            # num_unsatisfied_requirements.  Note that this shouldn't usually cause a deadlock, assuming no
            # circular requirements, because no other process will see this work unit as a requirer of target in
            # a call to work_succeeded() on target.
            # It can cause a deadlock if we try to add a requirement A -> B where both A and B are requirers
            # of some third work unit C, and work_succeeded() is called concurrently on C.
            try:
                target_wu = (
                    WorkUnit.objects.filter(pk=target_pk).exclude(state=WorkUnit.SUCCEEDED).select_for_update().get()
                )
                self.num_unsatisfied_requirements += 1
                if target_wu.state == WorkUnit.INFEASIBLE:
                    self._transition_to_state(WorkUnit.INFEASIBLE)
                elif self.state != WorkUnit.PENDING:
                    self._transition_to_state(WorkUnit.PENDING)
            except WorkUnit.DoesNotExist:
                pass
        return created

    @property
    def is_leased(self) -> bool:
        return self.state == self.LEASED

    def create_requirements(
        self, requirement_payload_objs: list[WorkUnitPayload], batch_size: int | None = None
    ) -> None:
        """A convenience method for creating new WorkUnits that are requirements of this work.

        Since we know that the created WorkUnits are new, we can make assumptions about them that allow us to set up the
        state efficiently, using bulk updates.
        """
        self._assert_state([WorkUnit.PENDING, WorkUnit.READY, WorkUnit.LEASED])

        if not requirement_payload_objs:
            return
        created_requirement_payload_objs = type(requirement_payload_objs[0]).objects.bulk_create(
            requirement_payload_objs, batch_size=batch_size
        )
        # We know the created_requirement_payload_objs are all in the READY state, and invisible outside this transaction.
        # So we can create the WorkUnitRequirement instances and update num_unsatisfied_requirements simply.
        requirements = [WorkUnitRequirement(source=self, target_id=obj.pk) for obj in created_requirement_payload_objs]
        WorkUnitRequirement.objects.bulk_create(requirements, batch_size=batch_size)
        self.num_unsatisfied_requirements += len(created_requirement_payload_objs)
        if self.state == WorkUnit.READY:
            self._transition_to_state(WorkUnit.PENDING)
        self.save()

    def requirement_satisfied(self, rerun_if_succeeded: bool = True) -> None:
        if self.state == self.PENDING:
            self.num_unsatisfied_requirements -= 1
            if self.num_unsatisfied_requirements == 0:
                if self.leased_until and self.leased_until > utcnow():
                    # We were rescheduled for some future time, and then also had a requirement added that is now satisfied.
                    # So return to the LEASED state, so we don't run again too soon.
                    self._transition_to_state(self.LEASED)
                else:
                    self._transition_to_state(self.READY)
        elif self.state == self.SUCCEEDED and rerun_if_succeeded:
            self.rerun()
        elif self.is_leased:
            # We might be LEASED because we rescheduled ourselves by time, and also added a requirement
            # that is now satisfied.
            self.num_unsatisfied_requirements -= 1
        elif self.state == self.INFEASIBLE:
            # We may have been marked as infeasible because a requirement failed, and now that
            # requirement has succeeded.  Or we may have been marked as infeasible for an unrelated
            # reason.  We can't tell those cases apart directly, but in the first case we should retry this work
            # (if there are no other infeasible requirements), and in the second case there is no harm in retrying.
            self.num_unsatisfied_requirements = self.requirements.exclude(state=self.SUCCEEDED).count()
            if self.num_unsatisfied_requirements == 0:
                self._transition_to_state(self.READY)
        # If self.state is READY then the requirement was re-run before this work had a chance to run,
        # so no need to do anything.

    def take_lease(self, until: datetime, last_attempt: datetime, node: str) -> None:
        self.leased_until = until
        self.lease_holder = str(uuid.uuid1())
        self.node = node
        self.last_attempt = last_attempt
        self.lease_taken()

    def lease_taken(self) -> None:
        self._assert_state(self.READY)
        self._transition_to_state(self.LEASED)

    def revoke_lease(self) -> None:
        self._assert_state(self.LEASED)
        new_state = self.READY if self.num_unsatisfied_requirements == 0 else self.PENDING
        self._transition_to_state(new_state)

    def work_succeeded(self, rerun_requirers: bool = True) -> None:
        self._assert_state(self.LEASED)
        self.succeeded_at = self.last_attempt
        self._transition_to_state(self.SUCCEEDED)

        # requirement_satisfied() will recalculate num_unsatisfied_requirements so it needs to see the correct state of this work unit.
        self.save()

        # Lock in pk order, to minimize deadlocks (postgres will acquire row locks in the specified order).
        requirers = WorkUnit.objects.filter(requirements=self).order_by("pk").select_for_update()
        for requirer in requirers:
            requirer.requirement_satisfied(rerun_if_succeeded=rerun_requirers)
            requirer.save()

    @classmethod
    def rerun_all(cls, payload_cls, from_date=None, to_date=None) -> None:
        """An efficient method for bulk-rerunning all work of a specific type.

        Can only be used if there is no PENDING work in the system.
        """
        with transaction.atomic():
            # First check that there's no PENDING work. If there is we might mess up the
            # num_unsatisfied_requirements counts.  See rerun() for details.
            cls._lock_table(transaction)
            if cls.objects.filter(state=cls.PENDING)[0:1].exists():
                raise ToolchainAssertion(
                    "Must not call WorkUnit.rerun_all() when there are outstanding PENDING WorkUnits."
                )

            payload_ctype = transaction.content_type_mgr.get_for_model(payload_cls)
            logger.info(f"Updating WorkUnit state {payload_cls}..")
            qs = cls.objects.filter(payload_ctype=payload_ctype, state=WorkUnit.SUCCEEDED)
            if from_date and to_date:
                qs = qs.filter(created_at__range=(from_date, to_date))
            elif from_date:
                qs = qs.filter(created_at__gte=from_date)
            elif to_date:
                qs = qs.filter(created_at__lte=to_date)
            num = qs.update(state=WorkUnit.READY)
            logger.info(f"Updated state for {num} WorkUnits, Performing state transition accounting...")
            WorkUnitStateCountDelta.objects.create(
                ctype=payload_ctype.id, from_state=cls.SUCCEEDED, to_state=cls.READY, delta=num
            )
        logger.info(f"rerun_all {num} for {payload_cls} - Done!")

    @classmethod
    def get_by_state(cls, payload_ctype: ContentType, state: str) -> QuerySet:
        if state not in cls.state_to_str:
            raise ToolchainAssertion(f"Invalid state: {state}")
        return cls.objects.filter(payload_ctype=payload_ctype, state=state)

    @classmethod
    def get_content_type_for_payload(cls, payload_cls: type) -> ContentType:
        return transaction.content_type_mgr.get_for_model(payload_cls)

    @classmethod
    def mark_all_as_feasible(cls, payload_cls: type) -> None:
        """An efficient method for bulk-marking all INFEASIBLE work of a specific type as FEASIBLE.

        Affects only INFEASIBLE work with no unsatisfied requirements.
        """
        try:
            payload_ctype = cls.get_content_type_for_payload(payload_cls)
            with transaction.atomic():
                # First check that there's no PENDING work. If there is we might mess up the
                # num_unsatisfied_requirements counts.  See rerun() for details.
                cls._lock_table(transaction)
                logger.info(f"Updating WorkUnit state for {payload_cls}.")
                qs = cls.get_by_state(payload_ctype, WorkUnit.INFEASIBLE).filter(num_unsatisfied_requirements=0)
                num = qs.update(state=WorkUnit.READY)
                logger.info(
                    f"Updated state for {num} WorkUnits of {payload_cls}. Performing state transition accounting."
                )
                WorkUnitStateCountDelta.objects.create(
                    ctype=payload_ctype.id, from_state=WorkUnit.INFEASIBLE, to_state=WorkUnit.READY, delta=num
                )
        except Exception as err:
            logger.exception(f"Error while marking work units of type {payload_cls} as feasible: {err!r}")
            raise
        logger.info(f"mark_all_as_feasible {payload_cls} - Done!")

    def rerun(self) -> None:
        self._assert_state(self.SUCCEEDED)
        # Lock in pk order, to minimize deadlocks (postgres will acquire row locks in the specified order).
        requirers = WorkUnit.objects.filter(requirements=self).order_by("pk").select_for_update()
        for requirer in requirers:
            if requirer.state == self.PENDING:
                # If the requirer is pending then when this workunit succeeds it will decrement the requirer's
                # num_unsatisfied_requirements, so we must increment it here.  If we don't, we may decrement the
                # count to zero even though the requirer is waiting on some other, unrelated requirement.
                requirer.num_unsatisfied_requirements += 1
                requirer.save()
        self._transition_to_state(self.READY)

    def permanent_error_occurred(self) -> None:
        self._assert_state(self.LEASED)
        transitive_requirer_pks: set[int] = set()
        self._gather_transitive_requirers(self.pk, transitive_requirer_pks)
        # Lock in pk order, to minimize deadlocks (postgres will acquire row locks in the specified order).
        # Note that we exclude any that are already INFEASIBLE (because of some other infeasible requirement).
        transitive_requirers = (
            WorkUnit.objects.filter(pk__in=transitive_requirer_pks)
            .exclude(state=self.INFEASIBLE)
            .order_by("pk")
            .select_for_update()
        )
        for requirer in transitive_requirers:
            requirer.has_infeasible_requirement()
        self._transition_to_state(self.INFEASIBLE)

    def has_infeasible_requirement(self) -> None:
        self._assert_state([self.PENDING, self.SUCCEEDED])  # Work is either waiting to be run or re-run.
        self._transition_to_state(self.INFEASIBLE)

    @classmethod
    def mark_as_feasible_for_ids(cls, work_unit_ids: set[int]) -> tuple[WorkUnit, ...]:
        with transaction.atomic():
            # Lock in pk order, to prevent deadlocks (postgres will acquire row locks in the specified order).
            work_units = (
                cls.objects.filter(pk__in=work_unit_ids, state=cls.INFEASIBLE).order_by("pk").select_for_update()
            )
            for work_unit in work_units:
                work_unit.mark_as_feasible()
        return tuple(work_units)

    def mark_as_feasible(self) -> None:
        self._assert_state(self.INFEASIBLE)
        new_state = self.READY if self.num_unsatisfied_requirements == 0 else self.PENDING
        self._transition_to_state(new_state)

    def check_num_unsatisfied_requirements(self) -> int | None:
        """Fix incorrect num_unsatisfied_requirements count presumably caused by a bug in the state- tracking
        algorithms."""
        self._assert_state([self.PENDING, self.INFEASIBLE])
        actual_num_unsatisfied_reqs = self.requirements.exclude(state=WorkUnit.SUCCEEDED).count()
        if self.num_unsatisfied_requirements != actual_num_unsatisfied_reqs:
            self.num_unsatisfied_requirements = actual_num_unsatisfied_reqs
            if actual_num_unsatisfied_reqs == 0 and self.state == self.PENDING:
                # All reqs have SUCCEEDED, so transition PENDING work to READY.
                self._transition_to_state(WorkUnit.READY)
            return actual_num_unsatisfied_reqs
        return None

    def _assert_state(self, allowed_states) -> None:
        if isinstance(allowed_states, str):
            allowed_states = [allowed_states]
            if self.state not in allowed_states:
                raise self.UnexpectedState(work_unit=self)

    def _transition_to_state(self, new_state: str) -> None:
        WorkUnitStateCountDelta.account_for_state_transition(self.payload, self.state, new_state)
        if self.state != new_state:
            ct = self.payload_ctype
            WORKUNIT_STATE_TRANSITION.labels(
                payload_model=ct.model,
                payload_app=ct.app_label,
                current_state=self.state_to_str[self.state],
                new_state=self.state_to_str[new_state],
            ).inc()
        self.state = new_state
        self.save()

    @classmethod
    def _gather_transitive_requirers(cls, work_unit_pk: int, ret: set[int]) -> None:
        direct_requirer_pks = set(cls.objects.filter(requirements=work_unit_pk).values_list("pk", flat=True))
        # There shouldn't be circular requirements, but we don't enforce that, and if there are any, we don't
        # want to recurse forever here, and we also don't want to raise an error, which will mask any underlying
        # error we're trying to handle in the caller.
        direct_requirer_pks -= {work_unit_pk}
        unhandled_pks = direct_requirer_pks - ret
        ret.update(direct_requirer_pks)
        for dr_pk in unhandled_pks:
            cls._gather_transitive_requirers(dr_pk, ret)

    def get_absolute_url(self):
        """Subclasses can override to customize the detail view in the workflow admin console."""
        return None

    def __str__(self) -> str:
        return f"{self.payload_ctype.model} {self.pk} ({self.description})"

    def get_ident(self) -> str:
        return f'{self.node}/{getattr(threading.current_thread(), "thread_number", "0")}'


class WorkUnitPayloadManager(Manager):
    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False):
        """Bulk create instances of the associated WorkUnitPayload type.

        Standard django bulk_create() doesn't call save() on created instances, or dispatch signals, so we apply the
        relevant logic here, in bulk.
        """
        if ignore_conflicts:
            raise ToolchainAssertion("Cannot bulk-create work unit payloads with ignore_conflicts=True.")
        with transaction.atomic():
            payload_ctype = transaction.content_type_mgr.get_for_model(self.model)
            created_at = utcnow()
            creator_id = get_calling_context()[1]
            # First bulk-create WorkUnit instances.
            work_units = [
                WorkUnit(
                    payload_ctype=payload_ctype,
                    description=obj.description,
                    creator_id=creator_id,
                    created_at=created_at,
                    search_vector=SearchVector(*(Value(x, output_field=TextField()) for x in obj.search_vector)),
                )
                for obj in objs
            ]
            # With PostgreSQL, Django sets autoincrement pks for bulk created instances (but only if ignore_conflicts=False).
            WorkUnit.objects.bulk_create(work_units, batch_size=batch_size, ignore_conflicts=False)
            # Set the pks on the payload objects.
            for obj, work_unit in zip(objs, work_units):
                obj.work_unit = work_unit
            # Bulk-create the payload objects.
            ret = super().bulk_create(objs, batch_size=batch_size, ignore_conflicts=False)
            # Do the stats accounting.
            WorkUnitStateCountDelta.objects.create(
                ctype=payload_ctype.id, from_state="", to_state=WorkUnit.READY, delta=len(objs)
            )
            return ret


class WorkUnitPayload(ToolchainModel):
    """A base class for the payload of work units.

    Subclass this to provide fields that describe a particular type of work.
    """

    objects = WorkUnitPayloadManager()

    class Meta:
        abstract = True

    work_unit = OneToOneField(WorkUnit, primary_key=True, on_delete=CASCADE, related_name="+")

    @property
    def description(self) -> str:
        """Subclasses can override to provide a useful description based on field values (except the pk field).

        Descriptions are searchable in workflow admin console.
        """
        return ""

    @property
    def search_vector(self) -> list[str]:
        """Subclasses can override to add strings to be searched on."""
        return [self.__class__.__name__, self.description]

    def add_requirement_by_id(self, work_unit_id: int) -> bool:
        with transaction.atomic():
            # Note that a work unit has the same pk as its payload.
            locked_work_unit = WorkUnit.locked(self.pk)
            created = locked_work_unit.add_requirement(work_unit_id)
            locked_work_unit.save()
            return created

    def _create_work_unit(self, creator_id: int) -> WorkUnit:
        search_vector = SearchVector(*(Value(x, output_field=TextField()) for x in self.search_vector))

        work_unit = WorkUnit.objects.create(
            payload_ctype=transaction.content_type_mgr.get_for_model(self),
            description=self.description,
            creator_id=creator_id,
            created_at=utcnow(),
            search_vector=search_vector,
        )
        self.work_unit = work_unit
        WorkUnitStateCountDelta.account_for_state_transition(self, None, work_unit.state)
        return work_unit

    def save(self, **kwargs):
        if self.pk is not None:
            return super().save(**kwargs)
        # This is a new object, so create a companion WorkUnit for it.
        creator_id = get_calling_context()[1]
        with transaction.atomic():
            self._create_work_unit(creator_id)
            return super().save(**kwargs)

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.description})"

    def rerun_work_unit(self) -> None:
        with transaction.atomic():
            self.work_unit.rerun()


class WorkUnitRequirement(ToolchainModel):
    """A work unit requirement.

    The source WorkUnit requires the target WorkUnit. In other words, the source WorkUnit cannot be worked on until the
    target WorkUnit has been completed successfully.

    Note that WorkUnitRequirement instances are never modified after insertion, so they should never be involved in
    deadlocks.

    IMPORTANT NOTE: Requirements must ONLY be set by calling the add() method. You should never create
    WorkUnitRequirement instances directly, as they will not be properly accounted for.
    """

    class Meta:
        unique_together = ("source", "target")

    id = AutoField(primary_key=True)
    source = ForeignKey(WorkUnit, db_index=True, on_delete=CASCADE, related_name="source+")
    target = ForeignKey(WorkUnit, db_index=True, on_delete=CASCADE, related_name="target+")

    def __repr__(self):
        return f"{self.source_id} -> {self.target_id}"


@dataclass(frozen=True, order=True)
class WorkUnitStateCountKey:
    ctype: int
    state: str


class WorkUnitStateCountDelta(ToolchainModel):
    """Delta to apply to WorkUnitStateCount.

    Transactions throw updates into this table, and a background process applies them after sorting to avoid deadlocks.
    This is more straightforward than attempting to track all state updates a transaction causes and sorting + applying
    them on commit.
    """

    id = AutoField(primary_key=True)

    # We don't use a ForeignKey field, for performance. There's no need to enforce a constraint
    # on this temporary table.
    ctype = IntegerField()

    # Indicates that delta should be subtracted from the count for from_state (if not blank)
    # and added to the count for to_state (if not blank).

    from_state = CharField(max_length=3, choices=WorkUnit.STATE_CHOICES, blank=True)

    to_state = CharField(max_length=3, choices=WorkUnit.STATE_CHOICES, blank=True)

    delta = IntegerField()

    @classmethod
    def account_for_state_transition(cls, payload_instance_or_type, from_state, to_state):
        """Modify stats to account for the transition between states.

        Expected to be called in a transaction.

        Use from_state=None to indicate a newly created work unit. Use to_state=None to indicate a deleted work unit
        (although we don't currently delete work units).
        """
        ctype = cls._ctype_id_for_instance_or_type(payload_instance_or_type)
        cls.objects.create(ctype=ctype, from_state=from_state or "", to_state=to_state or "", delta=1)

    @classmethod
    def apply(cls, n):
        """Apply up to n deltas to the main count table.

        :return: the number of deltas applied.
        """
        with transaction.atomic():
            logger.debug("Getting deltas.")
            rows = cls.objects.all()[0:n].select_for_update(skip_locked=True)
            # Aggregate them in memory to minimize db updates.
            logger.debug("Aggregating deltas.")
            key_to_delta = defaultdict(int)  # WorkUnitStateCountKey -> delta.
            pks = []
            for row in rows:
                if row.from_state:
                    key_to_delta[WorkUnitStateCountKey(row.ctype, row.from_state)] -= row.delta
                if row.to_state:
                    key_to_delta[WorkUnitStateCountKey(row.ctype, row.to_state)] += row.delta
                pks.append(row.pk)

            logger.debug("Applying deltas.")
            WorkUnitStateCount.apply_deltas(key_to_delta)
            # We already hold locks on all these rows, and no other process is attempting to
            # lock them, so we can delete them without concern for deadlocks.
            logger.debug("Deleting deltas.")
            cls.objects.filter(pk__in=sorted(pks)).delete()
        return len(pks)

    @staticmethod
    def _ctype_id_for_instance_or_type(instance_or_type):
        if isinstance(instance_or_type, int):
            # This is already a ctype id.
            return instance_or_type
        return transaction.content_type_mgr.get_for_model(instance_or_type, for_concrete_model=False).pk


class WorkUnitStateCount(ToolchainModel):
    """Counts of each work unit type in each state."""

    class Meta:
        unique_together = ("shard", "ctype", "state")

    # We shard rows to avoid lock contention.
    # Note that it's fine to change NUM_SHARDS at any time (even to reduce it).
    # No special migration is required.  It merely bounds the range in which
    # an update can randomly pick a shard.
    NUM_SHARDS = 50

    id = AutoField(primary_key=True)
    shard = IntegerField()

    ctype = ForeignKey(ContentType, on_delete=CASCADE, related_name="workunit_state_counts")

    state = CharField(max_length=3, choices=WorkUnit.STATE_CHOICES)

    count = IntegerField(default=0)

    @classmethod
    def apply_deltas(cls, key_to_delta):
        """Apply deltas to states.

        Call this in a transaction that also deletes the delta records.

        :param key_to_delta: map from WorkUnitStateCountKey to delta to add for that pair.
        """
        shard = random.randint(0, cls.NUM_SHARDS)  # nosec: B311

        # Sort, to avoid deadlocks.
        items = sorted(key_to_delta.items())
        for key, delta in items:

            def update():
                return cls.objects.filter(shard=shard, ctype_id=key.ctype, state=key.state).update(  # noqa: B023
                    count=F("count") + delta  # noqa: B023
                )

            if update() == 0:
                cls.objects.get_or_create(shard=shard, ctype_id=key.ctype, state=key.state)
                update()

    @classmethod
    def recompute(cls):
        """Recompute the counts from the raw work unit data.

        IMPORTANT: Only call this when the system is quiescent, and in particular when there
                   are no rows in the WorkUnitStateCountDelta table.
        """
        logger.info("Recomputing work unit state counts...")
        with Timer() as timer:
            try:
                with transaction.atomic():
                    cursor = transaction.connection.cursor()
                    logger.info("Locking WorkUnitStateCount table...")
                    cursor.execute(f"LOCK TABLE {WorkUnitStateCount._meta.db_table} IN EXCLUSIVE MODE")
                    logger.info("WorkUnitStateCount table locked!")
                    logger.info("Locking WorkUnitStateCountDelta table...")
                    cursor.execute(f"LOCK TABLE {WorkUnitStateCountDelta._meta.db_table} IN EXCLUSIVE MODE")
                    logger.info("WorkUnitStateCountDelta table locked!")
                    if WorkUnitStateCountDelta.objects.all()[0:1].exists():
                        raise ToolchainAssertion(
                            "Must not call WorkUnitStateCount.recompute() when there are "
                            "outstanding WorkUnitStateCountDeltas."
                        )
                    WorkUnitStateCount.objects.all().delete()
                    wuscs = [
                        WorkUnitStateCount(shard=0, ctype_id=x["payload_ctype"], state=x["state"], count=x["count"])
                        for x in WorkUnit.objects.values("payload_ctype", "state").annotate(count=Count("*"))
                    ]
                    WorkUnitStateCount.objects.bulk_create(wuscs)
                    logger.info(f"Recomputed work unit state counts in {timer.elapsed:.3f}s")
            except Exception as err:
                logger.exception(f"Error while recomputing work unit state counts: {err!r}")
                raise

    @classmethod
    def get_counts_by_model_and_state(cls) -> dict[str, dict[str, int]]:
        value_map: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for row in WorkUnitStateCount.objects.values("ctype__model", "state").annotate(count=Sum("count")):
            state_str = WorkUnit.state_to_str[row["state"]]
            value_map[row["ctype__model"]][state_str] = row["count"]
        return value_map

    @staticmethod
    def _ctype_for_instance_or_type(instance_or_type):
        if isinstance(instance_or_type, int):
            # This is already a ctype id.
            return instance_or_type
        return transaction.content_type_mgr.get_for_model(instance_or_type, for_concrete_model=False)

    def __repr__(self) -> str:
        return f"({self.ctype.model}, {self.state}) #{self.shard}: {self.count}"


class WorkExceptionLog(ToolchainModel):
    """A log of an exception encountered while performing work."""

    class Meta:
        indexes = [GinIndex(fields=["search_vector"])]

    id = AutoField(primary_key=True)
    timestamp = DateTimeField(default=utcnow, db_index=True)

    category = CharField(max_length=20, choices=WorkException.Category.get_choices())

    work_unit = ForeignKey(WorkUnit, related_name="errors", db_index=True, on_delete=CASCADE)

    message = CharField(max_length=50000)

    # Tab-separated strings representing stack frames.  We use tab and not newline because the
    # text of the frames may contain embedded newlines.
    stacktrace = TextField(blank=True)

    search_vector = SearchVectorField(null=True)

    @classmethod
    def create(
        cls, category: WorkExceptionCategory, work_unit: WorkUnit, error: Exception, stacktrace: str
    ) -> WorkExceptionLog:
        message = str(error)[:50000]
        wu_ident = work_unit.get_ident()
        entry = cls(category=category.value, work_unit=work_unit, message=message, stacktrace=stacktrace)
        logger.warning(f"[{wu_ident}] type={type(error)} {entry}")
        try:
            entry.save()
        except DbError as dbe:
            logger.exception(
                f"[{wu_ident}] Failed to log the following error in the WorkExceptionLog: {entry}.\nDue to: {dbe}"
            )
        return entry

    def stacktrace_frames(self, limit=None):
        """Return a list of short strings representing stack frames for the exception.

        :param limit: If specified, return this many innermost stack frames.
                      Otherwise, return all stack frames.
        """

        # Create a succinct representation of a stack frame.
        def shorten(frame):
            # Each frame contains multiple lines, but the first line is the one we care about,
            # that is, the one containing the file:lineno information.
            line_info = frame.split("\n")[0]

            # Remove uninteresting path prefixes, for brevity.
            def remove_prefix(s, prefix_ends_with):
                p = s.find(prefix_ends_with)
                if p >= 0:
                    return s[p + len(prefix_ends_with) :]
                return s

            # Remove the path/to/wheel/file.whl/ prefix from 3rdparty code paths.
            short = remove_prefix(line_info, ".whl/")
            # Remove the path/to/src/python/ prefix from local code paths.
            short = remove_prefix(short, "/src/python/")
            return short

        ret = [shorten(f) for f in self.stacktrace.split("\t")]
        if limit is not None:
            ret = ret[len(ret) - limit :]
        return ret

    def __str__(self):
        stacktrace_frames_str = "\n".join(self.stacktrace_frames())
        return f"{self.timestamp}: {self.category} on {self.work_unit}: {self.message} at {stacktrace_frames_str}"
