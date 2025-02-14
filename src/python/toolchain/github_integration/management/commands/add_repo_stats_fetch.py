# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.core.management.base import BaseCommand

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.site.models import Customer
from toolchain.github_integration.models import GithubRepo, GithubRepoStatsConfiguration


class Command(BaseCommand):
    help = "Add a worker that fetches stats from a GitHub repo at a given interval"

    def handle(self, *args, **options) -> None:
        self.do_command(minutes_opt=options["minutes"], repo_slug=options["repo"])

    def do_command(self, minutes_opt: str, repo_slug: str) -> None:
        if minutes_opt.lower() == "none":
            period_minutes = None
        else:
            period_minutes = int(minutes_opt)

        customer_slug, _, repo_slug = repo_slug.partition("/")
        customer = Customer.for_slug(customer_slug)
        if not customer:
            raise ToolchainAssertion(f"Invalid customer slug: {customer_slug}")
        github_repo = GithubRepo.get_or_none(customer_id=customer.id, name=repo_slug)

        if not github_repo:
            raise ToolchainAssertion(f"Invalid repo: {repo_slug}")

        GithubRepoStatsConfiguration.create(repo_id=github_repo.repo_id, period_minutes=period_minutes)

    def add_arguments(self, parser):
        parser.add_argument(
            "--minutes", required=True, help="Request frequency (in minutes), or 'none' for a one-off stats fetch"
        )
        parser.add_argument("--repo", required=True, help="GitHub Repo in format `github-org/repo-name`")
