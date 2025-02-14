# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json

import boto3


def create_fake_secret(*, region: str, name: str, secret: dict) -> None:
    client = boto3.client("secretsmanager", region_name=region)
    client.create_secret(Name=name, SecretString=json.dumps(secret))
