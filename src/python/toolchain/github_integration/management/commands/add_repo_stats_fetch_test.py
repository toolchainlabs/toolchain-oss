# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.django.site.models import Customer, Repo
from toolchain.github_integration.management.commands.add_repo_stats_fetch import Command
from toolchain.github_integration.models import GithubRepo, GithubRepoStatsConfiguration


class FakeCommand(Command):
    def handle(self, *args, **options):
        raise AssertionError("This code is for unit test only")


@pytest.mark.django_db()
class TestAddRepoStatsFetchCommand:
    def test_add_repo_stats_fetch(self) -> None:
        customer = Customer.create(slug="whatley", name="dentist")
        Repo.create("ovaltine", customer=customer, name="bania")
        GithubRepo.activate_or_create(
            repo_id="jerry", install_id="chicken", repo_name="ovaltine", customer_id=customer.id
        )

        Repo.create("seinfeld-reference", customer=customer, name="Repo2")
        GithubRepo.activate_or_create(
            repo_id="somerepoid", install_id="someinstallid", repo_name="seinfeld-reference", customer_id=customer.id
        )

        cmd = FakeCommand()
        cmd.do_command(repo_slug="whatley/ovaltine", minutes_opt="200")
        cmd.do_command(repo_slug="whatley/seinfeld-reference", minutes_opt="None")

        assert GithubRepoStatsConfiguration.objects.count() == 2
        ghcf1 = GithubRepoStatsConfiguration.objects.all()[0]
        ghcf2 = GithubRepoStatsConfiguration.objects.all()[1]
        assert ghcf1.period_minutes == 200
        assert ghcf2.period_minutes is None
