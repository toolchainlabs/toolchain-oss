# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
import re

from toolchain.aws.aws_api import AWSService
from toolchain.base.toolchain_error import ToolchainAssertion


class InvalidSecretNameError(ToolchainAssertion):
    pass


class SecretNotFoundError(ToolchainAssertion):
    pass


_logger = logging.getLogger(__name__)


class SecretsManager(AWSService):
    service = "secretsmanager"

    def create_secret(self, secret_name: str) -> None:
        """Creates a blank secret with the given name."""
        self.validate_secret_name(secret_name)
        self.client.create_secret(Name=secret_name)

    def get_secret(self, secret_name: str) -> str | None:
        """Returns the secret value as a character string."""
        try:
            res = self.client.get_secret_value(SecretId=secret_name)
            # This class always writes to SecretString, but we look at SecretBinary as well,
            # in case the secret we're reading was written by some other code.
            return res.get("SecretString") or res.get("SecretBinary").decode("utf8")
        except self.client.exceptions.ResourceNotFoundException:
            _logger.warning(f"Secret '{secret_name}' not found.")
            return None

    def set_secret(self, secret_name: str, value: str, create_if_nonexistent: bool = True) -> None:
        """Sets the secret value as a character string."""
        try:
            self.client.put_secret_value(SecretId=secret_name, SecretString=value)
        except self.client.exceptions.ResourceNotFoundException:
            if create_if_nonexistent:
                self.create_secret(secret_name)
                self.set_secret(secret_name, value, False)
            else:
                raise SecretNotFoundError(f"No such secret: {secret_name}")

    # See the error message below, which is a direct quote from the AWS documentation.
    _secret_name_re = re.compile(r"^[\w/+=.@-]+$")

    @classmethod
    def validate_secret_name(cls, secret_name: str) -> None:
        """Validate that the secret name will be accepted by AWS."""
        if len(secret_name) > 256:
            raise InvalidSecretNameError(f"AWS secret name must be no longer than 256 characters : {secret_name}")
        if cls._secret_name_re.match(secret_name) is None:
            raise InvalidSecretNameError(f"AWS secret name must be ASCII letters, digits, or /_+=.@- : {secret_name}")
        if len(secret_name) >= 7 and secret_name[-7] == "-":
            # As recommended by the AWS documentation, to avoid confusion with randomly generated suffixes.
            raise InvalidSecretNameError(
                f"AWS secret name must not end with a hyphen followed by six characters : {secret_name}"
            )
