# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging

from django.core.management.base import BaseCommand

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.site.models import Customer, Repo
from toolchain.github_integration.models import ConfigureGithubRepo, GithubRepo

_logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Deactivate github repos in our system"

    def add_arguments(self, parser):
        parser.add_argument("--no-dry-run", action="store_true", required=False, default=False, help="Dry run.")
        parser.add_argument("--slug", required=True, help="customer & repo slug")

    def handle(self, *args, **options):
        self.deactivate_repo(options["slug"], no_dry_run=options["no_dry_run"])

    def deactivate_repo(self, slug: str, no_dry_run=bool):
        customer_slug, _, repo_slug = slug.partition("/")
        customer = Customer.for_slug(customer_slug)
        if not customer:
            raise ToolchainAssertion(f"Invalid customer slug: {customer_slug}")
        github_repo = GithubRepo.get_or_none(customer_id=customer.id, name=repo_slug)
        repo = Repo.get_by_slug_and_customer_id(customer_id=customer.id, slug=repo_slug)
        if repo:
            repo.deactivate()
        else:
            _logger.warning(f"Repo {slug=} not found or not active")
        if not github_repo:
            _logger.warning(f"GithubRepo {slug=} not found or not active")
        github_repo.deactivate()
        ConfigureGithubRepo.create(github_repo.id)
