# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.aws.aws_api import AWSService


def test_convert_tags() -> None:
    aws_tags = [{"Key": "app", "Value": "buildsense-api"}, {"Key": "env", "Value": "toolchain_dev"}]
    assert AWSService.tags_to_dict(aws_tags) == {"app": "buildsense-api", "env": "toolchain_dev"}
