# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import os
from pathlib import Path

import pytest

from toolchain.config.services import get_service
from toolchain.util.prod.helm_charts import ServiceChartInfo


@pytest.mark.parametrize(
    ("service_name", "expected_chart_name", "expected_chart_path"),
    [
        ("infosite", "infosite", "infosite/infosite"),
        ("buildsense/api", "buildsense-api", "buildsense/api/buildsense-api"),
        ("toolshed", "toolshed", "toolshed/toolshed"),
        ("users/ui", "users-ui", "users/ui/users-ui"),
        ("users/api", "users-api", "users/api/users-api"),
        ("servicerouter", "servicerouter", "servicerouter/servicerouter"),
    ],
)
def test_service_info(service_name, expected_chart_name, expected_chart_path):
    sci = ServiceChartInfo.for_service(get_service(service_name))
    assert sci.service_name == service_name
    assert sci.chart_name == expected_chart_name
    assert sci.chart_path.as_posix() == f"prod/helm/services/{expected_chart_path}"
    assert os.path.isdir(sci.chart_path)
    chart_file = os.path.join(sci.chart_path, "Chart.yaml")
    assert os.path.isfile(chart_file)
    assert Path(chart_file).exists()
