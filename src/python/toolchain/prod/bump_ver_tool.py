#!/usr/bin/env ./python
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
from argparse import ArgumentParser, Namespace

from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.config.services import extrapolate_services
from toolchain.util.prod.helm_charts import HelmChart, ServiceChartInfo

_logger = logging.getLogger(__name__)


class BumpChartsVersions(ToolchainBinary):
    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._services = cmd_args.services

    def _bump_version(self, service) -> None:
        chart_path = ServiceChartInfo.for_service(service).chart_path
        chart = HelmChart.for_path(chart_path)
        chart.increment_chart_version()

    def run(self) -> int:
        for service in extrapolate_services(self._services):
            self._bump_version(service)
        return 0

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        parser.add_argument("services", nargs="+")


if __name__ == "__main__":
    BumpChartsVersions.start()
