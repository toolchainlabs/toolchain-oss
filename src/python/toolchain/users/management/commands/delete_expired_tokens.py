# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
from collections import defaultdict
from collections.abc import Sequence

from django.core.management.base import BaseCommand

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.site.models import AllocatedRefreshToken, Customer, ToolchainUser


class Command(BaseCommand):
    help = "Deletes expired refresh tokens from DB"

    def handle(self, *args, **options):
        dry_run = not options["no_dry_run"]
        customer_slug = options["customer"]
        if customer_slug != "*":
            customer = Customer.for_slug(slug=customer_slug)
            if not customer:
                raise ToolchainAssertion(f"No customer for {customer_slug=}")
        else:
            customer = None

        threshold = utcnow() - datetime.timedelta(days=options["threshold_days"])
        tokens_to_delete = self._get_tokens_to_delete(
            customer, AllocatedRefreshToken.get_expired_or_revoked_tokens(expiration_deletetion_threshold=threshold)
        )
        if not dry_run:
            for token in tokens_to_delete:
                token.delete()
        self.stdout.write(
            self.style.NOTICE(f"Delete {len(tokens_to_delete)} tokens. threshold: {threshold} dry run: {dry_run}")
        )

    def _get_tokens_to_delete(
        self, customer: Customer | None, tokens: Sequence[AllocatedRefreshToken]
    ) -> list[AllocatedRefreshToken]:
        users_to_tokens: dict[str, list[AllocatedRefreshToken]] = defaultdict(list)
        for token in tokens:
            users_to_tokens[token.user_api_id].append(token)
        users = ToolchainUser.with_api_ids(user_api_ids=list(users_to_tokens.keys()), include_inactive=True)
        tokens_to_delete = []
        for user in users:
            user_tokens = users_to_tokens[user.api_id]
            if not customer:
                tokens_to_delete.extend(user_tokens)
            elif user.customers.filter(id=customer.id).exists():
                tokens_to_delete.extend(user_tokens)
        return tokens_to_delete

    def add_arguments(self, parser):
        parser.add_argument(
            "--threshold-days",
            type=int,
            required=False,
            default=30,
            help="Expiration date threshold in days (relative to current date)",
        )
        parser.add_argument("--no-dry-run", action="store_true", required=False, default=False, help="Disable dry run.")
        parser.add_argument(
            "--customer",
            type=str,
            required=True,
            help="Delete only for users associated with a given customer (slug), specify `*` disable",
        )
