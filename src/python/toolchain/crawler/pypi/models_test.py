# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import pytest

from toolchain.crawler.pypi.models import DumpDistributionData, ProcessChangelog
from toolchain.packagerepo.pypi.models import Distribution, Project, Release
from toolchain.workflow.work_dispatcher_test import mark_work_unit_success


@pytest.mark.django_db()
class TestProcessChangelog:
    def test_create(self):
        assert ProcessChangelog.objects.count() == 0
        ProcessChangelog.create(serial_from=8901, serial_to=9000)
        assert ProcessChangelog.objects.count() == 1
        pcl = ProcessChangelog.objects.first()
        assert pcl.serial_from == 8901
        assert pcl.serial_to == 9000
        assert pcl.num_distributions_added is None
        assert pcl.num_distributions_removed is None
        assert pcl.distributions_added.count() == 0
        assert pcl.distributions_removed.count() == 0

    def _create_dist_objects(self) -> tuple[Distribution, ...]:
        project_1 = Project.get_or_create("databricks-connect")
        project_2 = Project.get_or_create("requests")
        dist_dict_1 = {
            "filename": "databricks-connect-6.3.1.tar.gz",
            "dist_type": "SDIST",
            "url": "https://files.pythonhosted.org/packages/fd/b4/databricks-connect-6.3.1.tar.gz",
            "digests": {"sha256": "07a5fb8ac1f41faa9f91eee04233f8906c64c71aab08e3e76f8f7956cb7a4999"},
        }
        dist_dict_2 = {
            "filename": "databricks-connect-6.7.1.tar.gz",
            "dist_type": "SDIST",
            "url": "https://files.pythonhosted.org/packages/fd/b4/databricks-connect-6.7.1.tar.gz",
            "digests": {"sha256": "not-important"},
        }
        dist_dict_3 = {
            "filename": "requests-2.2.0.tar.gz",
            "dist_type": "SDIST",
            "url": "https://files.pythonhosted.org/packages/fd/b4/requests-2.2.0.tar.gz",
            "digests": {"sha256": "bosco"},
        }
        dist_1 = Distribution.get_or_create_from_dict(
            dist_dict_1, Release.get_or_create(project_1, "6.3.1"), serial_from=70
        )
        dist_2 = Distribution.get_or_create_from_dict(
            dist_dict_2, Release.get_or_create(project_1, "6.7.1"), serial_from=77
        )
        dist_3 = Distribution.get_or_create_from_dict(
            dist_dict_3, Release.get_or_create(project_2, "2.2.0"), serial_from=55
        )
        return dist_1, dist_2, dist_3

    def test_update_processed_dists(self):
        pcl = ProcessChangelog.create(serial_from=30, serial_to=80)
        d1, d2, d3 = self._create_dist_objects()
        pcl.update_processed_dists(added=[d3, d1], removed=[d2])
        pcl.save()
        assert ProcessChangelog.objects.count() == 1
        pcl = ProcessChangelog.objects.first()
        assert pcl.serial_from == 30
        assert pcl.serial_to == 80
        assert pcl.num_distributions_added == 2
        assert pcl.num_distributions_removed == 1
        assert pcl.distributions_added.count() == 2
        assert pcl.distributions_removed.count() == 1
        assert pcl.distributions_removed.first() == d2
        assert set(pcl.distributions_added.all()) == {d3, d1}


@pytest.mark.django_db()
class TestDumpDistributionData:
    def _bootstap_existing_dumps(self):
        def create(serial_from, serial_to):
            payload = DumpDistributionData.objects.create(
                serial_from=serial_to,
                serial_to=serial_to,
                shard=0,
                num_shards=1,
                bucket="bubble-boy",
                key_prefix="he lives in a bubble.",
            )
            mark_work_unit_success(payload)

        create(serial_from=29, serial_to=88)
        create(serial_from=89, serial_to=100)
        create(serial_from=101, serial_to=115)

    def test_trigger_incremental_defaults(self):
        self._bootstap_existing_dumps()
        assert DumpDistributionData.objects.count() == 3
        mark_work_unit_success(ProcessChangelog.create(serial_from=10, serial_to=200))
        payload = DumpDistributionData.trigger_incremental()
        assert DumpDistributionData.objects.count() == 4
        assert payload == DumpDistributionData.objects.latest("work_unit_id")
        assert payload.serial_from == 115
        assert payload.serial_to == 200
        assert payload.bucket == "jambalaya"
        assert (
            payload.key_prefix
            == "seinfeld/no-soup-for-you/data_dumps/python_distribution_data/115-200/python_distribution_data"
        )
        assert payload.num_shards == 1
        assert payload.shard == 0

    def test_trigger_incremental_with_values(self):
        assert DumpDistributionData.objects.count() == 0
        payload = DumpDistributionData.trigger_incremental(serial_from=120, serial_to=250)
        assert DumpDistributionData.objects.count() == 1
        assert payload == DumpDistributionData.objects.first()
        assert payload.serial_from == 120
        assert payload.serial_to == 250
        assert payload.bucket == "jambalaya"
        assert (
            payload.key_prefix
            == "seinfeld/no-soup-for-you/data_dumps/python_distribution_data/120-250/python_distribution_data"
        )
        assert payload.num_shards == 1
        assert payload.shard == 0
