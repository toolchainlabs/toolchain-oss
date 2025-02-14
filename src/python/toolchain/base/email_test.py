# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.base.email import InvalidEmailError, parse_email


@pytest.mark.parametrize(
    ("email", "user", "domain"),
    [("jerry@ovaltine.com", "jerry", "ovaltine.com"), ("jerry+local@nbc.org", "jerry+local", "nbc.org")],
)
def test_valid_email(email, user, domain):
    assert parse_email(email) == (user, domain)


@pytest.mark.parametrize(
    "email", ["jerry+ovaltine.com", "jerry@ovalt@ine.com", "je@rry@ovaltine.com", "jerry@ovalti@ne"]
)
def test_invalid_email(email):
    with pytest.raises(InvalidEmailError, match="Invalid email"):
        parse_email(email)
