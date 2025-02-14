# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime

import pytest
from freezegun import freeze_time

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.github_integration.models import ConfigureGithubRepo, GithubRepo, GithubRepoStatsConfiguration, RepoState


@pytest.mark.django_db()
class TestGithubRepo:
    def test_activate_create(self):
        assert GithubRepo.objects.count() == 0
        now = utcnow()
        repo = GithubRepo.activate_or_create(
            install_id="77332", repo_id="8833", repo_name="tinsel", customer_id="no-soup-4u"
        )
        assert GithubRepo.objects.count() == 1
        loaded_repo = GithubRepo.objects.first()
        assert loaded_repo == repo
        assert loaded_repo.webhook_id == repo.webhook_id == ""
        assert repo.created_at == loaded_repo.created_at
        assert repo.id == loaded_repo.id
        assert repo.state == loaded_repo.state == RepoState.ACTIVE
        assert repo.is_active is True
        assert repo.customer_id == loaded_repo.customer_id == "no-soup-4u"
        assert repo.name == loaded_repo.name == "tinsel"
        assert repo.install_id == loaded_repo.install_id == "77332"
        assert loaded_repo.created_at.timestamp() == pytest.approx(now.timestamp())
        assert len(loaded_repo.webhooks_secret) == 64
        assert loaded_repo.webhooks_secret == repo.webhooks_secret
        assert loaded_repo.last_updated.timestamp() == pytest.approx(now.timestamp())
        assert loaded_repo.last_updated >= repo.created_at

    def test_activate_different_customer(self):
        now = utcnow()
        repo = GithubRepo.activate_or_create(
            install_id="77332", repo_id="92281", repo_name="tinsel", customer_id="no-soup-4u"
        )
        with pytest.raises(ToolchainAssertion, match="moved between customers"):
            GithubRepo.activate_or_create(
                install_id="9983332", repo_id="92281", repo_name="chicken", customer_id="festivus"
            )
        assert GithubRepo.objects.count() == 1
        loaded_repo = GithubRepo.objects.first()
        assert loaded_repo == repo
        assert loaded_repo.webhook_id == ""
        assert loaded_repo.state == RepoState.ACTIVE
        assert loaded_repo.is_active is True
        assert loaded_repo.customer_id == "no-soup-4u"
        assert loaded_repo.name == "tinsel"
        assert loaded_repo.install_id == "77332"
        assert repo.id == loaded_repo.id
        assert repo.created_at.timestamp() == pytest.approx(now.timestamp())
        assert repo.created_at == loaded_repo.created_at
        assert loaded_repo.webhooks_secret == repo.webhooks_secret
        assert loaded_repo.last_updated.timestamp() == pytest.approx(now.timestamp())
        assert loaded_repo.last_updated >= repo.created_at

    def test_activate_already_active(self):
        assert GithubRepo.objects.count() == 0
        dt = datetime.datetime(2020, 9, 2, 16, 3, tzinfo=datetime.timezone.utc)
        with freeze_time(dt):
            repo = GithubRepo.activate_or_create(
                install_id="2992", repo_id="9902", repo_name="pole", customer_id="ovaltine"
            )
        assert repo.created_at == repo.last_updated == dt
        assert GithubRepo.objects.count() == 1
        repo_2 = GithubRepo.activate_or_create(
            install_id="887337", repo_id="9902", repo_name="tinel", customer_id="ovaltine"
        )
        assert GithubRepo.objects.count() == 1
        loaded = GithubRepo.objects.first()
        assert loaded.created_at == dt
        assert loaded.last_updated.timestamp() == pytest.approx(utcnow().timestamp())
        assert loaded.webhooks_secret == repo_2.webhooks_secret == repo.webhooks_secret
        assert loaded.install_id == repo_2.install_id == "887337"
        assert loaded.name == repo_2.name == "tinel"
        assert loaded.customer_id == repo.customer_id == repo_2.customer_id == "ovaltine"

    def test_deactivate_active(self):
        dt = datetime.datetime(2020, 9, 2, 16, 3, tzinfo=datetime.timezone.utc)
        with freeze_time(dt):
            repo = GithubRepo.activate_or_create(
                install_id="2992", repo_id="9902", repo_name="pole", customer_id="ovaltine"
            )
        assert repo.deactivate() is True
        assert repo.created_at == dt
        assert repo.last_updated.timestamp() == pytest.approx(utcnow().timestamp())
        repo = GithubRepo.get_or_none(repo_id="9902")
        assert repo.state == GithubRepo.State.INACTIVE
        assert repo.is_active is False

    def test_deactivate_inactive(self):
        dt = datetime.datetime(2020, 9, 2, 16, 3, tzinfo=datetime.timezone.utc)
        with freeze_time(dt):
            repo = GithubRepo.activate_or_create(
                install_id="2992", repo_id="9902", repo_name="pole", customer_id="ovaltine"
            )
            repo.deactivate()
        assert GithubRepo.objects.count() == 1
        repo = GithubRepo.objects.first()
        assert repo.state == GithubRepo.State.INACTIVE
        assert repo.is_active is False
        assert repo.deactivate() is False
        assert GithubRepo.objects.count() == 1
        loaded = GithubRepo.objects.first()
        assert loaded.state == GithubRepo.State.INACTIVE
        assert loaded.is_active is False
        assert loaded.created_at == loaded.last_updated == dt

    def test_get_by_github_repo_id(self):
        assert GithubRepo.get_by_github_repo_id("9902") is None
        repo = GithubRepo.activate_or_create(
            install_id="2992", repo_id="9902", repo_name="pole", customer_id="ovaltine"
        )
        assert GithubRepo.get_by_github_repo_id("938402") is None
        assert GithubRepo.get_by_github_repo_id("9902") == repo
        repo.deactivate()
        assert GithubRepo.get_by_github_repo_id("9902") is None

    def test_get_webhook_secret(self):
        assert GithubRepo.get_webhook_secret(9902) is None
        repo = GithubRepo.activate_or_create(
            install_id="2992", repo_id="9902", repo_name="pole", customer_id="ovaltine"
        )
        assert GithubRepo.get_webhook_secret(8833) is None
        secret = GithubRepo.get_webhook_secret(9902)
        assert len(secret) == 64
        assert repo.webhooks_secret == secret
        assert GithubRepo.get_by_github_repo_id("9902").deactivate() is True
        assert GithubRepo.get_webhook_secret(9902) is None

    def test_get_by_id(self):
        assert GithubRepo.get_by_id("bosco") is None
        repo = GithubRepo.activate_or_create(
            install_id="2992", repo_id="9902", repo_name="pole", customer_id="ovaltine"
        )
        assert GithubRepo.get_by_id("bosco") is None
        assert GithubRepo.get_by_id("9902") is None
        assert GithubRepo.get_by_id(repo.id) == repo
        repo.deactivate()
        assert GithubRepo.get_by_id(repo.id) == repo

    def test_activate_create_long_name(self):
        assert GithubRepo.objects.count() == 0
        now = utcnow()
        repo = GithubRepo.activate_or_create(
            install_id="75388645993",
            repo_id="676353272",
            repo_name="jerry-just-remember-it’s-not-a-lie-if-you-believe-it",
            customer_id="no-soup-4u",
        )
        assert GithubRepo.objects.count() == 1
        loaded_repo = GithubRepo.objects.first()
        assert loaded_repo == repo
        assert loaded_repo.webhook_id == repo.webhook_id == ""
        assert repo.created_at == loaded_repo.created_at
        assert repo.id == loaded_repo.id
        assert repo.state == loaded_repo.state == RepoState.ACTIVE
        assert repo.is_active is True
        assert repo.customer_id == loaded_repo.customer_id == "no-soup-4u"
        assert repo.name == loaded_repo.name == "jerry-just-remember-it’s-not-a-lie-if-you-believe-it"
        assert repo.install_id == loaded_repo.install_id == "75388645993"
        assert loaded_repo.created_at.timestamp() == pytest.approx(now.timestamp())
        assert len(loaded_repo.webhooks_secret) == 64
        assert loaded_repo.webhooks_secret == repo.webhooks_secret
        assert loaded_repo.last_updated.timestamp() == pytest.approx(now.timestamp())
        assert loaded_repo.last_updated >= repo.created_at


@pytest.mark.django_db()
class TestGithubRepoStatsConfiguration:
    def test_github_repo_stats_configuration(self) -> None:
        assert GithubRepoStatsConfiguration.objects.count() == 0
        GithubRepoStatsConfiguration.create(repo_id="123", period_minutes=None)
        assert GithubRepoStatsConfiguration.objects.count() == 1
        grsc = GithubRepoStatsConfiguration.objects.first()
        assert grsc.repo_id == "123"
        assert grsc.period_minutes is None


@pytest.mark.django_db()
class TestConfigureGithubRepo:
    def test_create(self) -> None:
        assert ConfigureGithubRepo.objects.count() == 0
        cfg_repo = ConfigureGithubRepo.create("jerry")
        assert ConfigureGithubRepo.objects.count() == 1
        loaded = ConfigureGithubRepo.objects.first()
        assert loaded.work_unit_id == cfg_repo.work_unit_id
        assert loaded.repo_id == cfg_repo.repo_id == "jerry"
        assert loaded.extra_events == cfg_repo.extra_events == tuple()
        assert loaded.force_update is False

    def test_extra_events(self) -> None:
        cfg_repo = ConfigureGithubRepo.create("jerry")
        cfg_repo._extra_events = "soup,chicken,jerry"
        cfg_repo.save()
        loaded = ConfigureGithubRepo.objects.first()
        assert loaded.extra_events == ("soup", "chicken", "jerry")

    def test_disable_force_update(self) -> None:
        ConfigureGithubRepo.create("jerry")
        loaded = ConfigureGithubRepo.objects.first()
        assert loaded.force_update is False
        loaded.disable_force_update()  # no-op
        assert loaded.force_update is False
        loaded.force_update = True
        loaded.save()
        loaded = ConfigureGithubRepo.objects.first()
        assert loaded.force_update is True
        loaded.disable_force_update()
        assert loaded.force_update is False
        loaded = ConfigureGithubRepo.objects.first()
        assert loaded.force_update is False
