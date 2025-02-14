# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from django.core.management.base import BaseCommand

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.buildsense.ingestion.models import ProcessBuildDataRetention
from toolchain.django.site.models import Customer, Repo


class Command(BaseCommand):
    help = "Sets buildsense data retention policy for a repo"

    def add_arguments(self, parser):
        parser.add_argument("--repo", type=str, required=True, default=None, help="customer/repo (slugs).")
        parser.add_argument("--days", type=int, required=True, help="Number of days to retain data")
        parser.add_argument("--period", type=int, required=False, default=None, help="Number of minutes between runs")
        parser.add_argument(
            "--no-dry-run", action="store_false", required=False, default=True, help="Disabled dry run."
        )

    def handle(self, *args, **options):
        days = options["days"]
        period = options["period"]
        dry_run = options["no_dry_run"]
        repo_full_name = options["repo"]
        customer_slug, _, repo_slug = repo_full_name.partition("/")
        if repo_slug == "*":
            customer = Customer.for_slug(slug=customer_slug, include_inactive=True)
            if not customer:
                raise ToolchainAssertion(f"Customer {customer_slug} ({repo_full_name}) not found)")
            repos = list(Repo.for_customer_id(customer_id=customer.id, include_inactive=True))
        else:
            single_repo = Repo.get_for_slugs_or_none(
                customer_slug=customer_slug, repo_slug=repo_slug, include_inactive=True
            )
            repos = [single_repo] if single_repo else []
        if not repos:
            raise ToolchainAssertion(f"Repo {repo_full_name} not found)")
        for repo in repos:
            ProcessBuildDataRetention.create_or_update_for_repo(
                repo=repo, retention_days=days, period_minutes=period, dry_run=dry_run
            )
