# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.conf import settings

from toolchain.aws.aws_api import AWSService


def configure_aws_for_django() -> None:
    if not hasattr(settings, "AWS_REGION"):
        return
    boto3_cfg = getattr(settings, "BOTO3_CONFIG", {})
    AWSService.set_default_config(settings.AWS_REGION, boto3_cfg)
