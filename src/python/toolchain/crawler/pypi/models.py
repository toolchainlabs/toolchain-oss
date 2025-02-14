# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from django.conf import settings
from django.db.models import (
    CASCADE,
    AutoField,
    BooleanField,
    CharField,
    DateTimeField,
    ForeignKey,
    IntegerField,
    ManyToManyField,
    Max,
    URLField,
)
from django.urls import reverse

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.crawler.pypi.data_dump_sharding import NUM_SHARDS_CHOICES, compute_seed_shards
from toolchain.django.db.base_models import ToolchainModel
from toolchain.django.db.transaction_broker import TransactionBroker
from toolchain.lang.python.distributions.distribution_type import DistributionType
from toolchain.packagerepo.pypi.models import Distribution
from toolchain.workflow.models import WorkUnit, WorkUnitPayload

transaction = TransactionBroker("crawlerpypi")


class ProcessAllProjects(WorkUnitPayload):
    """Process all projects, as part of a full crawl."""

    created_at = DateTimeField(db_index=True)
    serial = IntegerField(db_index=True)
    num_shards = IntegerField()

    @property
    def description(self) -> str:
        return f"@{self.serial}"

    def get_absolute_url(self) -> str:
        return reverse("crawler:processallprojects_detail", args=[self.pk])


class ProcessAllProjectsShard(WorkUnitPayload):
    """Process a shard of projects.

    Exists as an intermediate level between ProcessAllProjects and ProcessProject: without this every ProcessProject
    that succeeds has to update the num_unsatisfied_requirements field on ProcessAllProjects's WorkUnit, and since there
    are ~200K projects at the time of writing, this creates huge contention that slows the end of the crawl down to a
    trickle.
    """

    class Meta:
        unique_together = [("process_all_projects", "shard_number")]

    process_all_projects = ForeignKey(ProcessAllProjects, on_delete=CASCADE, related_name="shards")
    shard_number = IntegerField()

    @property
    def description(self) -> str:
        return f"@{self.process_all_projects.serial} shard #{self.shard_number}"

    def get_absolute_url(self) -> str:
        return reverse("crawler:processallprojectsshard_detail", args=[self.pk])


class ProcessProject(WorkUnitPayload):
    """Process all releases in a project, as part of a full crawl."""

    project_name = CharField(max_length=100, db_index=True)
    required_serial = IntegerField()

    # The distributions found when processing.  Initially empty, filled in by the processing worker.
    distributions = ManyToManyField(Distribution, through="ProcessProjectDistribution", related_name="processed_by")
    # Some projects have no distributions, so we can't tell if we've scheduled distribution processing
    # just by looking at the `distributions` field (it can be empty even if we done so). So we use
    # this nullable field instead.
    num_distributions = IntegerField(null=True)

    @property
    def description(self) -> str:
        return f"{self.project_name} @{self.required_serial}"

    def get_absolute_url(self) -> str:
        return reverse("crawler:processproject_detail", args=[self.pk])


class ProcessProjectDistribution(ToolchainModel):
    """M2M Map from a ProcessProject to the distributions it found when processing."""

    id = AutoField(primary_key=True)
    process_project = ForeignKey(ProcessProject, on_delete=CASCADE)
    distribution = ForeignKey(Distribution, on_delete=CASCADE)


class ProcessDistribution(WorkUnitPayload):
    """Extract metadata from a distribution."""

    processable_dist_types = {DistributionType.WHEEL.value, DistributionType.BDIST.value, DistributionType.SDIST.value}

    distribution = ForeignKey(Distribution, on_delete=CASCADE, db_index=True)

    @classmethod
    def get_or_create(cls, distribution: Distribution) -> ProcessDistribution:
        return cls.objects.get_or_create(distribution=distribution)[0]

    @property
    def description(self):
        return self.distribution.filename

    def get_absolute_url(self) -> str:
        return reverse("crawler:processdistribution_detail", args=[self.pk])


class PeriodicallyProcessChangelog(WorkUnitPayload):
    # Check changelog every this many minutes (or None for one-time processing).
    period_minutes = IntegerField(null=True)

    def get_absolute_url(self) -> str:
        return reverse("crawler:periodicallyprocesschangelog_detail", args=[self.pk])

    @property
    def description(self) -> str:
        return f"period_min={self.period_minutes}"


class ProcessChangelog(WorkUnitPayload):
    serial_from = IntegerField(db_index=True)
    serial_to = IntegerField(db_index=True)
    # The distributions found when processing.  Initially empty, filled in by the processing worker.
    distributions_added = ManyToManyField(Distribution, through="ProcessChangelogAdded", related_name="added_by")
    distributions_removed = ManyToManyField(Distribution, through="ProcessChangelogRemoved", related_name="removed_by")
    # Some changelog spans may have no distributions, so we can't tell if we've scheduled distribution processing
    # just by looking at the m2m fields (they can be empty even if we have done so). So we use these nullable fields instead.
    num_distributions_added = IntegerField(null=True)
    num_distributions_removed = IntegerField(null=True)

    @classmethod
    def create(cls, *, serial_from: int, serial_to: int) -> ProcessChangelog:
        return cls.objects.create(serial_from=serial_from, serial_to=serial_to)

    def update_processed_dists(self, *, added: list[Distribution], removed: list[Distribution]) -> None:
        self.distributions_added.set(added)
        self.num_distributions_added = len(added)
        self.distributions_removed.set(removed)
        self.num_distributions_removed = len(removed)

    def get_absolute_url(self) -> str:
        return reverse("crawler:processchangelog_detail", args=[self.pk])

    @property
    def description(self) -> str:
        changes = self.serial_to - self.serial_from
        return f"{changes=} from={self.serial_from} to={self.serial_to}"


class ProcessChangelogAdded(ToolchainModel):
    """M2M Map from a ProcessChangelog to the distributions it added when processing."""

    id = AutoField(primary_key=True)
    process_changelog = ForeignKey(ProcessChangelog, on_delete=CASCADE)
    distribution = ForeignKey(Distribution, on_delete=CASCADE)


class ProcessChangelogRemoved(ToolchainModel):
    """M2M Map from a ProcessChangelog to the distributions it removed when processing."""

    id = AutoField(primary_key=True)
    process_changelog = ForeignKey(ProcessChangelog, on_delete=CASCADE)
    distribution = ForeignKey(Distribution, on_delete=CASCADE)


class DumpDistributionData(WorkUnitPayload):
    """Dump data for a shard's worth of distributions to S3."""

    shard = IntegerField()
    num_shards = IntegerField(choices=[(num, "num") for num in NUM_SHARDS_CHOICES])
    bucket = CharField(max_length=64)
    serial_from = IntegerField(db_index=True)
    serial_to = IntegerField(db_index=True)
    # We'll suffix the key with <shard number>.tgz.
    key_prefix = CharField(max_length=512)

    @classmethod
    def trigger_full(cls, num_shards: int = 256, concurrency: int = 1) -> list[DumpDistributionData]:
        return cls._create_shards(num_shards, concurrency, 0)

    @classmethod
    def trigger_incremental(cls, serial_from: int | None = None, serial_to: int | None = None) -> DumpDistributionData:
        serial_from = (
            serial_from
            or cls.objects.filter(work_unit__state=WorkUnit.SUCCEEDED).aggregate(Max("serial_to"))["serial_to__max"]
            or 0
        )
        if serial_from == 0:
            raise ToolchainAssertion("At least one successful full or incremental dump required.")
        return cls._create_shards(1, 1, serial_from, serial_to)[0]

    @classmethod
    def _create_shards(
        cls, num_shards: int, concurrency: int, serial_from: int, serial_to: int | None = None
    ) -> list[DumpDistributionData]:
        serial_to = serial_to or most_recent_complete_serial()
        seed_shards = compute_seed_shards(num_shards, concurrency)
        bucket = settings.WEBRESOURCE_BUCKET
        key_prefix = (
            f"{settings.WEBRESOURCE_KEY_PREFIX}/data_dumps/python_distribution_data/{serial_from}-{serial_to}/"
            f"python_distribution_data"
        )
        seed_objects = [
            cls(
                shard=shard,
                num_shards=num_shards,
                bucket=bucket,
                serial_from=serial_from,
                serial_to=serial_to,
                key_prefix=key_prefix,
            )
            for shard in seed_shards
        ]
        return cls.objects.bulk_create(seed_objects)

    def get_absolute_url(self) -> str:
        return reverse("crawler:dumpdistributiondata_detail", args=[self.pk])


class UpdateLevelDb(WorkUnitPayload):
    """Update (or create) a leveldb."""

    input_dir_url = URLField(max_length=500)  # Look for input data in this S3 dir.
    output_dir_url = URLField(max_length=500)  # Output the leveldb to this S3 dir.
    existing_leveldb_dir_url = URLField(max_length=500, default="")  # If this leveldb exists, use its data as a base.
    builder_cls = CharField(max_length=100)  # Name of subclass of toolchain.util.leveldb.builder.Builder.

    @classmethod
    def create(
        cls, *, input_dir_url: str, output_dir_url: str, existing_leveldb_dir_url: str | None, builder_cls: str
    ) -> UpdateLevelDb:
        return cls.objects.create(
            input_dir_url=input_dir_url,
            output_dir_url=output_dir_url,
            existing_leveldb_dir_url=existing_leveldb_dir_url or "",
            builder_cls=builder_cls,
        )

    @property
    def description(self) -> str:
        return f"{self.builder_cls} - output_dir_url={self.output_dir_url}"


class PeriodicallyUpdateLevelDb(WorkUnitPayload):
    """Periodically trigger UpdateLevelDb."""

    # Trigger UpdateLevelDb every this many minutes (or None for one-time processing).
    period_minutes = IntegerField(null=True)
    # Triggers a full rebuild of LevelDBs, the worker will set this back to False once a full rebuild is triggered.
    rebuild = BooleanField(default=False)
    input_dir_url = URLField(max_length=500)  # Look for input data in this S3 dir.
    output_dir_base_url = URLField(max_length=500)  # Parent of versioned leveldb output dirs.
    builder_cls = CharField(max_length=100)  # Name of subclass of toolchain.util.leveldb.builder.Builder.

    def disable_rebuild(self) -> bool:
        """Disable the rebuild flag if it is set.

        Returns True if it did otherwise False.
        """
        if self.rebuild is False:
            return False
        self.rebuild = False
        self.save()
        return True

    @property
    def description(self) -> str:
        return f"{self.builder_cls} - period_min={self.period_minutes} rebuild={self.rebuild}"


def most_recent_complete_serial() -> int:
    """Return the most recent serial for which we definitely have all data."""

    def max_qs(payload_cls: type[ProcessAllProjects] | type[ProcessChangelog], field_name: str) -> int:
        qs = payload_cls.objects.filter(work_unit__state=WorkUnit.SUCCEEDED)
        return qs.aggregate(Max(field_name))[f"{field_name}__max"] or 0

    serial = max(max_qs(ProcessChangelog, "serial_to"), max_qs(ProcessAllProjects, "serial"))
    if serial == 0:
        raise ToolchainAssertion("At least one successful full or incremental crawl required.")
    return serial
