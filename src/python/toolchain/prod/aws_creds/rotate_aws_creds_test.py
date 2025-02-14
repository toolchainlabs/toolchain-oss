# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import textwrap

from toolchain.aws.iam import IAMAccessKey
from toolchain.prod.aws_creds.rotate_aws_creds import RotateAWSCreds


def test_rewriting_credentials() -> None:
    rotator = RotateAWSCreds.create_for_args(aws_region="ap-northeast-1", deactivate_access_key=False)
    existing_creds = textwrap.dedent(
        """
    # This is a comment and should be passed through.
    [default]
    aws_access_key_id = rotate-me-please
    aws_secret_access_key = this-should-get-rotated-too

    [some-other-profile]
    aws_access_key_id = do-not-touch-this
    aws_secret_access_key = do-not-touch-this
    """
    )

    new_access_key = IAMAccessKey(user_name="cramer", access_key_id="festivus", secret_access_key="george")
    actual_new_creds = rotator._rewrite_creds(
        existing_creds, "rotate-me-please", "this-should-get-rotated-too", new_access_key
    )
    expected_new_creds = textwrap.dedent(
        """
    # This is a comment and should be passed through.
    [default]
    aws_access_key_id = festivus
    aws_secret_access_key = george

    [some-other-profile]
    aws_access_key_id = do-not-touch-this
    aws_secret_access_key = do-not-touch-this
    """
    )
    assert actual_new_creds == expected_new_creds
