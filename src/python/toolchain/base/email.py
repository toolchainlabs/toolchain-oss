# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.base.toolchain_error import ToolchainAssertion


class InvalidEmailError(ToolchainAssertion):
    pass


def parse_email(email):
    user, _, domain = email.partition("@")
    if not domain or "@" in domain or "@" in user:
        raise InvalidEmailError(f"Invalid email: {email}")
    return user, domain
