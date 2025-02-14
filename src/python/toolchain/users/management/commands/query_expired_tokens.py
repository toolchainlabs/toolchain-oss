# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
from collections import Counter

from django.core.management.base import BaseCommand
from rich.console import Console
from rich.table import Table

from toolchain.base.datetime_tools import utcnow
from toolchain.django.site.models import AllocatedRefreshToken, Customer, ToolchainUser


class Command(BaseCommand):
    help = "Deletes expired refresh tokens from DB"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._customers_cache: dict[str, Customer] = {}

    def _get_customer_slug(self, user: ToolchainUser) -> str:
        customers_ids = user.customers_ids
        if not customers_ids:
            return "N/A"
        customer_id = customers_ids[0]
        if customer_id not in self._customers_cache:
            self._customers_cache[customer_id] = Customer.objects.get(id=customer_id)
        return self._customers_cache[customer_id].slug

    def handle(self, *args, **options):
        threshold = utcnow() - datetime.timedelta(days=options["threshold_days"])
        tokens_qs = AllocatedRefreshToken.get_expired_or_revoked_tokens(expiration_deletetion_threshold=threshold)
        user_token_count = Counter(token.user_api_id for token in tokens_qs)
        users = ToolchainUser.with_api_ids(user_api_ids=user_token_count.keys(), include_inactive=True)

        table = Table(
            "User",
            "Customer",
            "Token Count",
            show_header=True,
            header_style="bold magenta",
        )
        for user in users:
            table.add_row(user.username, self._get_customer_slug(user), str(user_token_count[user.api_id]))
        console = Console()
        console.print(table)
        console.print(f"Total expired tokens for threshold {threshold.date()}: {tokens_qs.count()}")

    def add_arguments(self, parser):
        parser.add_argument(
            "--threshold-days",
            type=int,
            required=False,
            default=30,
            help="Expiration date threshold in days (relative to current date)",
        )
