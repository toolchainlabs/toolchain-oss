# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
from enum import Enum, unique

import shortuuid
from django.db.models import CharField, DateTimeField, DurationField, PositiveIntegerField, Q, QuerySet

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.db.base_models import ToolchainModel
from toolchain.django.db.transaction_broker import TransactionBroker
from toolchain.django.util.helpers import get_choices
from toolchain.workflow.models import WorkUnitPayload

transaction = TransactionBroker("pants_demos")
_logger = logging.getLogger(__name__)


@unique
class RepoProcessingState(Enum):
    NOT_PROCESSED = "not_processed"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILURE = "failure"

    @property
    def display_name(self) -> str:
        return self.value.replace("_", " ").capitalize()


class DemoRepo(ToolchainModel):
    State = RepoProcessingState
    MAX_SLUG_LENGTH = 256
    id = CharField(max_length=22, primary_key=True, default=shortuuid.uuid, unique=True, db_index=True, editable=False)
    repo_account = CharField(max_length=MAX_SLUG_LENGTH)
    repo_name = CharField(max_length=MAX_SLUG_LENGTH)
    created_at = DateTimeField(default=utcnow, editable=False)
    last_processed = DateTimeField(null=True)
    result_location = CharField(max_length=256)  # s3 url
    commit_sha = CharField(max_length=48)
    branch_name = CharField(max_length=48)
    fail_reason = CharField(max_length=256)
    _processing_state = CharField(
        max_length=15,
        default=RepoProcessingState.NOT_PROCESSED.value,
        db_column="state",
        choices=get_choices(RepoProcessingState),
    )
    # num of targets we got via ./pants peek is a good high level indicator so it is worth to have it on the model.
    num_of_targets = PositiveIntegerField(null=True)
    processing_time = DurationField(null=True, default=None)

    class Meta:
        unique_together = ("repo_account", "repo_name")

    @classmethod
    def create(cls, account: str, repo: str) -> DemoRepo:
        dr = cls.get_or_none(repo_account__iexact=account, repo_name__iexact=repo)
        if not dr:
            dr, created = cls.objects.get_or_create(repo_account=account, repo_name=repo)
            if created:
                _logger.info(f"Created DemoRepo {dr}")
                GenerateDepgraphForRepo.objects.create(demo_repo_id=dr.id)
        return dr

    @classmethod
    def get_successful_qs(cls, excludes: frozenset[str]) -> QuerySet:
        qs = cls.objects.filter(_processing_state=RepoProcessingState.SUCCESS.value).order_by("-last_processed")
        # This code assumes that the number of excludes is low. so it is fine to create q query with all of those exludes.
        if len(excludes) > 10:
            raise ToolchainAssertion("Number of excludes exceeds max allowed")
        for repo_fn in sorted(excludes or []):
            account, _, repo = repo_fn.partition("/")
            qs = qs.exclude(Q(repo_account=account, repo_name=repo))

        return qs

    @property
    def repo_full_name(self) -> str:
        return f"{self.repo_account}/{self.repo_name}"

    @property
    def processing_state(self) -> RepoProcessingState:
        return RepoProcessingState(self._processing_state)

    @property
    def is_completed(self) -> bool:
        return self.processing_state in {RepoProcessingState.SUCCESS, RepoProcessingState.FAILURE}

    @property
    def is_successful(self) -> bool:
        return self.processing_state == RepoProcessingState.SUCCESS

    @property
    def is_failed(self) -> bool:
        return self.processing_state == RepoProcessingState.FAILURE

    def __str__(self) -> str:
        return f"{self.repo_full_name} id={self.id}"

    def start_processing(self, s3_url: str) -> None:
        self.result_location = s3_url
        self.last_processed = utcnow()
        self._processing_state = RepoProcessingState.PROCESSING.value
        self.save()

    def set_success_result(
        self, *, branch: str, commit_sha: str, num_of_targets: int, processing_time: datetime.timedelta | None
    ) -> None:
        self._processing_state = RepoProcessingState.SUCCESS.value
        self.branch_name = branch
        self.commit_sha = commit_sha
        self.num_of_targets = num_of_targets
        self.processing_time = processing_time
        _logger.info(
            f"repo: {self.repo_full_name} - success. {branch=} {commit_sha=} {num_of_targets=} {processing_time=}"
        )
        self.save()

    def set_failure_result(self, *, reason: str, processing_time: datetime.timedelta | None) -> None:
        self._processing_state = RepoProcessingState.FAILURE.value
        self.fail_reason = reason
        self.processing_time = processing_time
        _logger.info(f"repo: {self.repo_full_name} - fail. {reason} {processing_time=}")
        self.save()


class GenerateDepgraphForRepo(WorkUnitPayload):
    demo_repo_id = CharField(max_length=22)

    @property
    def description(self) -> str:
        return f"GenerateDepgraphForRepo demo_repo_id={self.demo_repo_id}"

    def __str__(self) -> str:
        return self.description
