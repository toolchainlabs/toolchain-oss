# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from botocore.exceptions import BotoCoreError, CredentialRetrievalError, EndpointConnectionError, NoCredentialsError
from urllib3.exceptions import HTTPError


def is_transient_aws_error(error: Exception) -> bool:
    if isinstance(error, HTTPError):
        # Boto uses urlib3 so any connection errors manifest themselves as urlib3 errors
        return True
    if not isinstance(error, BotoCoreError):
        # Not a boto error
        return False
    if isinstance(error, (EndpointConnectionError, CredentialRetrievalError)):
        return True
    if isinstance(error, NoCredentialsError):
        return "unable to locate credentials" in str(error).lower()
    return False
