# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator

import shortuuid
from django.db.models import BooleanField, CharField, DateTimeField, IntegerField

from toolchain.base.datetime_tools import utcnow
from toolchain.base.password import generate_password
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.db.base_models import ToolchainModel
from toolchain.django.db.transaction_broker import TransactionBroker
from toolchain.github_integration.common.constants import RepoState
from toolchain.workflow.models import WorkUnitPayload

transaction = TransactionBroker("github_integration")

_logger = logging.getLogger(__name__)


class GithubRepo(ToolchainModel):
    State = RepoState
    id = CharField(max_length=22, default=shortuuid.uuid, primary_key=True, db_index=True, editable=False)
    # The ID github allocates for the repo.
    repo_id = CharField(max_length=10, db_index=True)
    _repo_state = CharField(
        max_length=10, default=RepoState.ACTIVE.value, db_index=True, null=False, db_column="repo_state"
    )
    name = CharField(max_length=64)  # repo name (slug), maps to django.sites.models.Repo
    customer_id = CharField(max_length=22)
    install_id = CharField(editable=False, max_length=64)  # The ID github allocates for the install.
    created_at = DateTimeField(default=utcnow, editable=False)
    webhooks_secret = CharField(max_length=64)
    last_updated = DateTimeField(default=utcnow)

    # Empty string we don't have a repo webhook registered.
    webhook_id = CharField(max_length=10, default="")

    @property
    def state(self) -> RepoState:
        return RepoState(self._repo_state)

    def _activate_for_install(self, install_id: str, name: str) -> None:
        self.name = name
        self.install_id = install_id
        self._activate()

    def _activate(self) -> None:
        prev_state = self.state
        self._repo_state = RepoState.ACTIVE.value
        _logger.info(f"Activate {self!r} - previous_state={prev_state}")
        self.save()

    def deactivate(self) -> bool:
        if self.state != RepoState.ACTIVE:
            _logger.warning(f"Repo {self!r} is not active.")
            return False
        self._repo_state = RepoState.INACTIVE.value
        _logger.info(f"Deactivate {self!r}")
        self.save()
        return True

    def set_state(self, is_active: bool) -> bool:
        if is_active:
            if self.is_active:
                return False
            self._activate()
            return True
        if not self.is_active:
            return False
        self.deactivate()
        return True

    def save(self, **kwargs):
        self.last_updated = utcnow()
        return super().save(**kwargs)

    @classmethod
    def get_for_customer_and_slug(cls, customer_id: str, repo_slug: str) -> GithubRepo | None:
        return cls.get_or_none(customer_id=customer_id, name=repo_slug, _repo_state=RepoState.ACTIVE.value)

    @classmethod
    def get_for_customer_id(cls, customer_id: str) -> list[GithubRepo]:
        qs = cls.objects.filter(customer_id=customer_id)
        return list(qs.order_by("name"))

    @classmethod
    def get_install_id_for_customer_id(cls, customer_id: str) -> str | None:
        qs = cls.objects.filter(customer_id=customer_id).order_by("-last_updated")
        latest_install = qs.first()
        return latest_install.install_id if latest_install else None

    @classmethod
    def get_for_installation(cls, customer_id: str, install_id: str) -> Iterator[GithubRepo]:
        qs = cls.objects.filter(customer_id=customer_id, install_id=install_id, _repo_state=RepoState.ACTIVE.value)
        return qs.iterator()

    @classmethod
    def get_by_github_repo_id(cls, repo_id: str) -> GithubRepo | None:
        return cls.get_or_none(repo_id=str(repo_id), _repo_state=RepoState.ACTIVE.value)

    @classmethod
    def get_by_id(cls, repo_id: str) -> GithubRepo | None:
        return cls.get_or_none(id=repo_id)

    @classmethod
    def activate_or_create(cls, *, repo_id: str, install_id: str, repo_name: str, customer_id: str) -> GithubRepo:
        repo = cls.get_or_none(repo_id=repo_id)
        if not repo:
            repo = cls(repo_id=repo_id, customer_id=customer_id, webhooks_secret=generate_password(64))
        else:
            if customer_id != repo.customer_id:
                raise ToolchainAssertion(
                    f"{repo!r} moved between customers ({repo.customer_id} -> {customer_id}). This is unexpected and not allowed."
                )
        repo._activate_for_install(install_id=install_id, name=repo_name)
        return repo

    @classmethod
    def get_webhook_secret(cls, github_repo_id: int) -> str | None:
        repo = cls.get_by_github_repo_id(str(github_repo_id))
        return repo.webhooks_secret if repo else None

    @property
    def is_active(self) -> bool:
        return self.state == RepoState.ACTIVE

    def __repr__(self) -> str:
        return (
            f"GithubRepo(repo_id={self.repo_id} state={self.state.value} install_id={self.install_id} name={self.name})"
        )


class ConfigureGithubRepo(WorkUnitPayload):
    repo_id = CharField(max_length=22, editable=False)
    _extra_events = CharField(max_length=128, editable=True, db_column="extra_events", default="")
    force_update = BooleanField(default=False)

    @classmethod
    def create(cls, repo_id: str) -> ConfigureGithubRepo:
        return cls.objects.create(repo_id=repo_id)

    @classmethod
    def bulk_create(cls, repos: Iterable[GithubRepo]) -> None:
        objects = [cls(repo_id=repo.id) for repo in repos]
        if not objects:
            return
        cls.objects.bulk_create(objects)

    @property
    def description(self) -> str:
        return f"ConfigureGithubRepo repo_id={self.repo_id} extra_events={self.extra_events}"

    @property
    def extra_events(self) -> tuple[str, ...]:
        return tuple(self._extra_events.split(",")) if self._extra_events else ()

    def disable_force_update(self) -> None:
        if not self.force_update:
            return
        self.force_update = False
        self.save()

    def __str__(self) -> str:
        return self.description


class GithubRepoStatsConfiguration(WorkUnitPayload):
    repo_id = CharField(max_length=22, editable=False)
    period_minutes = IntegerField(null=True)

    @classmethod
    def create(cls, repo_id: str, period_minutes: int | None) -> GithubRepoStatsConfiguration:
        return cls.objects.create(repo_id=repo_id, period_minutes=period_minutes)

    @property
    def description(self) -> str:
        return f"GithubRepoStatsConfiguration repo_id={self.repo_id} period={self.period_minutes}min"


_MODELS_TO_CHECK = (GithubRepoStatsConfiguration, ConfigureGithubRepo, GithubRepo)


def check_models_read_access():
    objects = {model.__name__: model.objects.first() for model in _MODELS_TO_CHECK}
    return {name: obj.pk if obj else "NA" for name, obj in objects.items()}
