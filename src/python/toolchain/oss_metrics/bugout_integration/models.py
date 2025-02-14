# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

from django.db.models import CharField, DateField, IntegerField

from toolchain.workflow.models import WorkUnit, WorkUnitPayload


class ScheduleBugoutDataDownload(WorkUnitPayload):
    period_minutes = IntegerField(null=True)
    journal_id = CharField(max_length=36, editable=False, unique=True)  # Bugout uses UUIDs.

    @classmethod
    def update_or_create(cls, period_minutes: int, journal_id: str) -> ScheduleBugoutDataDownload:
        obj, _ = cls.objects.update_or_create(journal_id=journal_id, defaults={"period_minutes": period_minutes})
        return obj

    @property
    def description(self) -> str:
        return f"journal_id={self.journal_id} period_minutes={self.period_minutes}"


class DownloadBugoutDataForDay(WorkUnitPayload):
    day = DateField(editable=False)
    journal_id = CharField(max_length=36, editable=False)  # Bugout uses UUIDs.

    class Meta:
        unique_together = ("day", "journal_id")

    @classmethod
    def run_for_date(cls, day: datetime.date, journal_id: str) -> DownloadBugoutDataForDay:
        obj, created = cls.objects.get_or_create(day=day, journal_id=journal_id)
        if not created and obj.work_unit.state == WorkUnit.SUCCEEDED:
            obj.rerun_work_unit()
        return obj

    @classmethod
    def get_latest_day_or_none(cls, journal_id: str) -> datetime.date | None:
        latest = cls.objects.filter(journal_id=journal_id).order_by("-day").first()
        return latest.day if latest else None

    @property
    def description(self) -> str:
        return f"journal_id={self.journal_id} day={self.day}"
