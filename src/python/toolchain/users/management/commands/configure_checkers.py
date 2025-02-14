# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.core.management.base import BaseCommand

from toolchain.users.models import PeriodicallyCheckAccessTokens, PeriodicallyRevokeTokens


class Command(BaseCommand):
    help = "Configures token checkers workers"

    def handle(self, *args, **options) -> None:
        check_interval = options["check_interval_hours"] * 60
        revoke_interval = options["revoke_interval_hours"] * 60
        max_tokens = options["max_token_revoke"]
        self.do_command(
            token_check_internval=check_interval, token_revoke_internval=revoke_interval, max_tokens=max_tokens
        )

    def do_command(
        self,
        token_check_internval: int,
        token_revoke_internval: int,
        max_tokens: int,
    ) -> None:
        PeriodicallyRevokeTokens.create_or_update(period_minutes=token_revoke_internval, max_tokens=max_tokens)
        PeriodicallyCheckAccessTokens.create_or_update(period_minutes=token_check_internval)

    def add_arguments(self, parser):
        parser.add_argument(
            "--check-interval-hours",
            type=int,
            required=False,
            default=12,
            help="Tokens check run interval (hours)",
        )

        parser.add_argument(
            "--revoke-interval-hours",
            required=False,
            type=int,
            default=8,
            help="Tokens revoker run interval (hours)",
        )
        parser.add_argument(
            "--max-token-revoke",
            type=int,
            required=False,
            default=10,
            help="Maximum tokens to revoke in a single run",
        )
