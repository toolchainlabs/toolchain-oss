# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import textwrap
from pathlib import Path

from toolchain.util.prod.helm_charts import HelmChart

CHART_DEF = textwrap.dedent(
    """\
    # Copyright © 2020 Toolchain Labs, Inc. All rights reserved.
    #
    # Toolchain Labs, Inc. CONFIDENTIAL
    #
    # This file includes unpublished proprietary source code of Toolchain Labs, Inc.
    # The copyright notice above does not evidence any actual or intended publication of such source code.
    # Disclosure of this source code or any related proprietary information is strictly prohibited without
    # the express written permission of Toolchain Labs, Inc.

    apiVersion: v2
    description: Dependency workflow maintenance service
    name: dependency-maintenance
    version: 88.22.77
    kubeVersion: ">=v1.18.0-0,<v1.23-0"
    dependencies:
    - name: django
      version: "*"
      repository: file://../../../django/
"""
)

CHART_DEF_NO_DEPS = textwrap.dedent(
    """\
    # Copyright © 2022 Toolchain Labs, Inc. All rights reserved.
    #
    # Toolchain Labs, Inc. CONFIDENTIAL
    #
    # This file includes unpublished proprietary source code of Toolchain Labs, Inc.
    # The copyright notice above does not evidence any actual or intended publication of such source code.
    # Disclosure of this source code or any related proprietary information is strictly prohibited without
    # the express written permission of Toolchain Labs, Inc.

    apiVersion: v2
    description: Dependency workflow maintenance service
    name: dependency-maintenance
    version: 88.22.77
    kubeVersion: ">=v1.18.0-0,<v1.23-0"
"""
)

VERSIONED_CHART_VALUES = textwrap.dedent(
    """\
    # Copyright © 2019 Toolchain Labs, Inc. All rights reserved.
    #
    # Toolchain Labs, Inc. CONFIDENTIAL
    #
    # This file includes unpublished proprietary source code of Toolchain Labs, Inc.
    # The copyright notice above does not evidence any actual or intended publication of such source code.
    # Disclosure of this source code or any related proprietary information is strictly prohibited without
    # the express written permission of Toolchain Labs, Inc.

    name: infosite
    gunicorn_image_rev:
      us-east-1: prod-2021-03-08.15-57-56-b52a0c2dccbb
    service_type: web-ui
    env: null
    service_location: edge
    iam_service_role_arn: null
"""
)


class TestHelmChart:
    def _prep_chart(self, tmp_path: Path, values_fixture: str, chart_fixture: str = CHART_DEF) -> Path:
        fake_chart_path = tmp_path / "festivus"
        fake_chart_path.mkdir(parents=True)
        values_file = fake_chart_path / "values.yaml"
        values_file.write_text(values_fixture)
        chart_file = fake_chart_path / "Chart.yaml"
        chart_file.write_text(chart_fixture)
        return fake_chart_path

    def test_save_values(self, tmp_path: Path) -> None:
        fake_chart_path = self._prep_chart(tmp_path, VERSIONED_CHART_VALUES)
        chart = HelmChart.for_path(fake_chart_path)
        values = chart.get_values(with_roundtrip=True)
        values["gunicorn_image_rev"]["us-east-1"] = "prod-2021-02-01.22-28-02-60f48e0759a2"
        chart.save_values(values)
        assert chart.get_values() == {
            "name": "infosite",
            "gunicorn_image_rev": {"us-east-1": "prod-2021-02-01.22-28-02-60f48e0759a2"},
            "service_type": "web-ui",
            "iam_service_role_arn": None,
            "env": None,
            "service_location": "edge",
        }
        values_text = (fake_chart_path / "values.yaml").read_text()
        assert values_text == textwrap.dedent(
            """\
        # Copyright © 2019 Toolchain Labs, Inc. All rights reserved.
        #
        # Toolchain Labs, Inc. CONFIDENTIAL
        #
        # This file includes unpublished proprietary source code of Toolchain Labs, Inc.
        # The copyright notice above does not evidence any actual or intended publication of such source code.
        # Disclosure of this source code or any related proprietary information is strictly prohibited without
        # the express written permission of Toolchain Labs, Inc.

        name: infosite
        gunicorn_image_rev:
          us-east-1: prod-2021-02-01.22-28-02-60f48e0759a2
        service_type: web-ui
        env: null
        service_location: edge
        iam_service_role_arn: null
    """
        )

    def test_get_values(self, tmp_path: Path) -> None:
        fake_chart_path = self._prep_chart(tmp_path, VERSIONED_CHART_VALUES)
        chart = HelmChart.for_path(fake_chart_path)
        assert chart.get_values() == {
            "name": "infosite",
            "gunicorn_image_rev": {"us-east-1": "prod-2021-03-08.15-57-56-b52a0c2dccbb"},
            "service_type": "web-ui",
            "iam_service_role_arn": None,
            "env": None,
            "service_location": "edge",
        }

    def test_update_chart_version(self, tmp_path: Path) -> None:
        fake_chart_path = self._prep_chart(tmp_path, VERSIONED_CHART_VALUES)
        chart = HelmChart.for_path(fake_chart_path)
        chart.update_chart_version("88.22.77")
        chart_def = (fake_chart_path / "Chart.yaml").read_text()
        assert chart_def == textwrap.dedent(
            """\
        # Copyright © 2020 Toolchain Labs, Inc. All rights reserved.
        #
        # Toolchain Labs, Inc. CONFIDENTIAL
        #
        # This file includes unpublished proprietary source code of Toolchain Labs, Inc.
        # The copyright notice above does not evidence any actual or intended publication of such source code.
        # Disclosure of this source code or any related proprietary information is strictly prohibited without
        # the express written permission of Toolchain Labs, Inc.

        apiVersion: v2
        description: Dependency workflow maintenance service
        name: dependency-maintenance
        version: 88.22.77
        kubeVersion: '>=v1.18.0-0,<v1.23-0'
        dependencies:
        - name: django
          version: '*'
          repository: file://../../../django/
    """
        )

    def test_increment_chart_version(self, tmp_path: Path) -> None:
        fake_chart_path = self._prep_chart(tmp_path, VERSIONED_CHART_VALUES)
        chart = HelmChart.for_path(fake_chart_path)
        chart.increment_chart_version()
        chart_def = (fake_chart_path / "Chart.yaml").read_text()
        assert chart_def == textwrap.dedent(
            """\
        # Copyright © 2020 Toolchain Labs, Inc. All rights reserved.
        #
        # Toolchain Labs, Inc. CONFIDENTIAL
        #
        # This file includes unpublished proprietary source code of Toolchain Labs, Inc.
        # The copyright notice above does not evidence any actual or intended publication of such source code.
        # Disclosure of this source code or any related proprietary information is strictly prohibited without
        # the express written permission of Toolchain Labs, Inc.

        apiVersion: v2
        description: Dependency workflow maintenance service
        name: dependency-maintenance
        version: 88.23.0
        kubeVersion: '>=v1.18.0-0,<v1.23-0'
        dependencies:
        - name: django
          version: '*'
          repository: file://../../../django/
        """
        )

    def test_has_depednencies(self, tmp_path: Path) -> None:
        cp = self._prep_chart(tmp_path / "ch1", VERSIONED_CHART_VALUES, CHART_DEF)
        assert HelmChart.for_path(cp).has_depednencies is True
        cp = self._prep_chart(tmp_path / "ch2", VERSIONED_CHART_VALUES, CHART_DEF_NO_DEPS)
        assert HelmChart.for_path(cp).has_depednencies is False
