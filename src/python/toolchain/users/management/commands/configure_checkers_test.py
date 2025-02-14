# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.users.management.commands.configure_checkers import Command
from toolchain.users.models import PeriodicallyCheckAccessTokens, PeriodicallyRevokeTokens


class FakeCommand(Command):
    def handle(self, *args, **options):
        raise AssertionError("This code is for unit test only")


@pytest.mark.django_db()
def test_configure_checks() -> None:
    assert PeriodicallyCheckAccessTokens.objects.count() == 0
    assert PeriodicallyRevokeTokens.objects.count() == 0
    cmd = FakeCommand()
    cmd.do_command(token_check_internval=12, token_revoke_internval=9, max_tokens=7)

    assert PeriodicallyCheckAccessTokens.objects.count() == 1
    assert PeriodicallyRevokeTokens.objects.count() == 1
    pcat = PeriodicallyCheckAccessTokens.objects.first()
    prt = PeriodicallyRevokeTokens.objects.first()
    assert prt.period_minutes == 9
    assert prt.max_tokens == 7
    assert pcat.period_minutes == 12

    cmd.do_command(token_check_internval=10, token_revoke_internval=20, max_tokens=30)
    assert PeriodicallyCheckAccessTokens.objects.count() == 1
    assert PeriodicallyRevokeTokens.objects.count() == 1
    pcat = PeriodicallyCheckAccessTokens.objects.first()
    prt = PeriodicallyRevokeTokens.objects.first()
    assert prt.period_minutes == 20
    assert prt.max_tokens == 30
    assert pcat.period_minutes == 10
