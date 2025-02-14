# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import boto3
import pytest
from moto import mock_efs

from toolchain.aws.efs import EFS
from toolchain.base.toolchain_error import ToolchainAssertion


def create_fake_efs(name: str) -> str:
    client = boto3.client("efs", region_name="ap-northeast-2")
    resp = client.create_file_system(Tags=[{"Key": "Name", "Value": name}])
    return resp["FileSystemId"]


@pytest.fixture(autouse=True)
def _start_moto():
    with mock_efs():
        yield


def test_get_file_system_id() -> None:
    fs_id = create_fake_efs("jerry")
    assert fs_id is not None
    efs = EFS("ap-northeast-2")
    assert efs.get_file_system_id("jerry") == fs_id


def test_get_file_system_id_not_found() -> None:
    fs_id = create_fake_efs("jerry")
    assert fs_id is not None
    efs = EFS("ap-northeast-2")
    with pytest.raises(ToolchainAssertion, match="Can't find EFS with name: newman. tried: "):
        efs.get_file_system_id("newman")
