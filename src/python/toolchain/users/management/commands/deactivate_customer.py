# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging

from django.core.management.base import BaseCommand

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.site.models import Customer, Repo

_logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Deactivate a customer, repo associated with it and any users that are only assoicated with that customer"

    def handle(self, *args, **options):
        slug = options["slug"]
        dry_run = options["no_dry_run"]
        customer = Customer.for_slug(slug=slug, include_inactive=True)
        if not customer:
            raise ToolchainAssertion(f"No customer with slug: {slug}")
        _logger.info(f"Deactivate {customer} {dry_run=}")
        if not dry_run:
            customer.deactivate()

        repos = Repo.for_customer_id(customer_id=customer.id, include_inactive=False)
        for repo in repos:
            _logger.info(f"Deactivate {repo} {dry_run=}")
            if not dry_run:
                repo.deactivate()
        users = customer.users.all()
        for user in users:
            if user.is_active is False:
                continue
            if user.is_associated_with_active_customers:
                _logger.info(f"Not deactivating {user} since it is associated with active customers")
                continue
            _logger.info(f"Deactivate {user} {dry_run=}")
            if not dry_run:
                user.deactivate()

    def add_arguments(self, parser):
        parser.add_argument("--slug", type=str, required=True, help="Customer slug")
        parser.add_argument(
            "--no-dry-run", action="store_false", required=False, default=True, help="Disabled dry run."
        )
