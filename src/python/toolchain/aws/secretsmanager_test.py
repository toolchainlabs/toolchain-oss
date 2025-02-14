# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.aws.secretsmanager import InvalidSecretNameError, SecretsManager


@pytest.mark.parametrize("secret_name", ["%foo", "foo*", "foo-012345", 257 * "X"])
def test_secret_name_invalid(secret_name):
    with pytest.raises(InvalidSecretNameError, match=r"AWS secret name must .+"):
        SecretsManager.validate_secret_name(secret_name)


@pytest.mark.parametrize("secret_name", ["foo", "@Foo.BAR1+2/4", "foo-01234", "foo-0123456", 256 * "X"])
def test_secret_name_valid(secret_name):
    SecretsManager.validate_secret_name(secret_name)
