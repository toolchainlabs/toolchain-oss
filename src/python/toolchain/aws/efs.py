# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from toolchain.aws.aws_api import AWSService
from toolchain.base.toolchain_error import ToolchainAssertion


class EFS(AWSService):
    service = "efs"

    def get_file_system_id(self, name: str) -> str:
        names = []
        paginator = self.client.get_paginator("describe_file_systems")
        for efs_page_data in paginator.paginate():
            for efs_data in efs_page_data["FileSystems"]:
                efs_name = efs_data["Name"]
                if efs_name == name:
                    return efs_data["FileSystemId"]
                names.append(efs_name)
        raise ToolchainAssertion(f"Can't find EFS with name: {name}. tried: {names}")
