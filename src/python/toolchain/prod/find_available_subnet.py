#!/usr/bin/env ./python
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
from argparse import ArgumentParser, Namespace

from toolchain.aws.ec2 import EC2
from toolchain.base.toolchain_binary import ToolchainBinary

_logger = logging.getLogger(__name__)


class FindAvailableSubnet(ToolchainBinary):
    description = "Finds a free netenum subnet"
    _NET_ENUM_INDEX = 2

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._ec2 = EC2(cmd_args.aws_region)
        self._count = cmd_args.count

    def run(self) -> int:
        subnets = self._ec2.get_subnets()
        used_subnets = {subnet.get_address_component(self._NET_ENUM_INDEX) for subnet in subnets}
        available_subnets: list[str] = []
        for net_enum in range(2, 254):
            if len(available_subnets) >= self._count:
                break
            if net_enum not in used_subnets:
                available_subnets.append(str(net_enum))
        if not available_subnets:
            _logger.error(f"Could not find available subnets. Total subnets: {len(used_subnets)}")
            return -1
        available_str = ", ".join(available_subnets)
        _logger.info(f"Found available subnet(s): {available_str}")
        return 0

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        cls.add_aws_region_argument(parser)
        parser.add_argument(
            "--count", type=int, default=3, metavar="int", required=False, help="Number of available subnets to find."
        )


if __name__ == "__main__":
    FindAvailableSubnet.start()
