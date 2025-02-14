# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import secrets
import string


def generate_password(length: int = 40) -> str:
    """Generates a random password."""
    return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(0, length))
