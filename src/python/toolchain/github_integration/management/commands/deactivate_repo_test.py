# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.django.site.models import Customer, Repo
from toolchain.github_integration.management.commands.deactivate_repo import Command
from toolchain.github_integration.models import ConfigureGithubRepo, GithubRepo


class FakeCommand(Command):
    def handle(self, *args, **options):
        raise AssertionError("This code is for unit test only")


@pytest.mark.django_db()
class TestDeactivateRepoCommand:
    def test_deactivate_repo(self) -> None:
        customer = Customer.create(slug="whatley", name="dentist")
        repo = Repo.create("ovaltine", customer=customer, name="bania")
        Repo.create("chicken", customer=customer, name="Little Jerry Seinfeld")
        GithubRepo.activate_or_create(
            repo_id="jerry", install_id="chicken", repo_name="ovaltine", customer_id=customer.id
        )
        cmd = FakeCommand()
        cmd.deactivate_repo(slug="whatley/ovaltine")
        assert Repo.objects.count() == 2
        assert Repo.base_qs().count() == 1
        assert GithubRepo.objects.count() == 1
        assert ConfigureGithubRepo.objects.count() == 1
        repo = Repo.objects.get(id=repo.id)
        assert repo.is_active is False
        assert Customer.objects.first().is_active is True
        gh_repo = GithubRepo.objects.first()
        assert gh_repo.state == GithubRepo.State.INACTIVE
        configure_repo = ConfigureGithubRepo.objects.first()
        assert configure_repo.repo_id == gh_repo.id

    def test_deactivate_repo_inactive_repo(self) -> None:
        customer = Customer.create(slug="whatley", name="dentist")
        repo = Repo.create("ovaltine", customer=customer, name="bania")
        repo.deactivate()
        GithubRepo.activate_or_create(
            repo_id="jerry", install_id="chicken", repo_name="ovaltine", customer_id=customer.id
        )
        cmd = FakeCommand()
        cmd.deactivate_repo(slug="whatley/ovaltine")
        assert Repo.objects.count() == 1
        assert Repo.base_qs().count() == 0
        assert GithubRepo.objects.count() == 1
        assert ConfigureGithubRepo.objects.count() == 1
        repo = Repo.objects.get(id=repo.id)
        assert repo.is_active is False
        assert Customer.objects.first().is_active is True
        gh_repo = GithubRepo.objects.first()
        assert gh_repo.state == GithubRepo.State.INACTIVE
        configure_repo = ConfigureGithubRepo.objects.first()
        assert configure_repo.repo_id == gh_repo.id
