# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime

import pytest
from moto import mock_s3

from toolchain.aws.s3 import S3
from toolchain.aws.test_utils.s3_utils import create_s3_bucket
from toolchain.base.datetime_tools import utcnow
from toolchain.crawler.base.models import FetchURL
from toolchain.crawler.pypi.models import ProcessDistribution
from toolchain.crawler.pypi.workers.distribution_processor import DistributionProcessor
from toolchain.django.webresource.models import WebResource
from toolchain.lang.python.test_helpers.utils import get_dist_binary_data
from toolchain.packagerepo.pypi.models import Distribution, DistributionData, Project, Release


@pytest.mark.django_db()
class TestDistributionProcessor:
    @pytest.fixture(autouse=True)
    def _start_moto(self, settings):
        with mock_s3():
            create_s3_bucket(settings.WEBRESOURCE_BUCKET)
            yield

    def _create_web_resource(self, distribution: Distribution) -> None:
        WebResource.objects.create(
            url=distribution.url,
            sha256_hexdigest="07a5fb8ac1f41faa9f91eee04233f8906c64c71aab08e3e76f8f7956cb7a4999",
            freshness=utcnow() - datetime.timedelta(days=20),
            encoding="",
            compression=WebResource.IDENTITY,
            content_url="s3://jambalaya/no-soup-for-you/databricks.dist",
            etag='"c70fcaa4abba16c1874c65a643e525f9"',
        )
        dist_data = get_dist_binary_data("databricks-connect-6.3.1.tar.gz")
        S3().upload_content(bucket="jambalaya", key="no-soup-for-you/databricks.dist", content_bytes=dist_data)

    def _create_dist_objects(self) -> Distribution:
        project = Project.get_or_create("databricks-connect")
        release = Release.get_or_create(project, "6.3.1")
        dist_dict = {
            "filename": "databricks-connect-6.3.1.tar.gz",
            "dist_type": "SDIST",
            "url": "https://files.pythonhosted.org/packages/fd/b4/3a1a1e45f24bde2a2986bb6e8096d545a5b24374f2cfe2b36ac5c7f30f4b/databricks-connect-6.3.1.tar.gz",
            "digests": {"sha256": "07a5fb8ac1f41faa9f91eee04233f8906c64c71aab08e3e76f8f7956cb7a4999"},
        }
        dist = Distribution.get_or_create_from_dict(dist_dict, release, serial_from=88221)

        return dist

    def test_process_distribution(self) -> None:
        dist = self._create_dist_objects()
        self._create_web_resource(dist)
        payload = ProcessDistribution.get_or_create(distribution=dist)
        worker = DistributionProcessor()
        assert DistributionData.objects.count() == 0

        assert worker.do_work(payload) is True
        assert DistributionData.objects.count() == 1
        dist_data = DistributionData.objects.first()
        assert dist_data.distribution_id == dist.id
        assert dist_data.distribution == dist
        # Just sampling, tests for data extraction logic are in lang/python
        assert len(dist_data.metadata) == 15
        assert dist_data.metadata["author"] == "Databricks"
        assert dist_data.metadata["provides_extras"] == ["ml", "mllib", "sql"]
        assert dist_data.metadata["provides"] == ["pyspark"]
        assert len(dist_data.modules) == 102
        assert dist_data.modules[:3] == [
            "pyspark",
            "pyspark.accumulators",
            "pyspark.broadcast",
        ]

    def test_process_distribution_no_web_resource(self) -> None:
        dist = self._create_dist_objects()
        payload = ProcessDistribution.get_or_create(distribution=dist)
        worker = DistributionProcessor()
        assert DistributionData.objects.count() == 0
        assert worker.do_work(payload) is False
        assert DistributionData.objects.count() == 0

    def test_on_reschedule(self) -> None:
        dist = self._create_dist_objects()
        payload = ProcessDistribution.get_or_create(distribution=dist)
        assert FetchURL.objects.count() == 0
        assert DistributionData.objects.count() == 0
        assert DistributionProcessor().on_reschedule(payload) is None
        assert DistributionData.objects.count() == 0
        assert FetchURL.objects.count() == 1
        fetch_url = FetchURL.objects.first()
        assert fetch_url.url == dist.url
        wu = payload.work_unit
        wu.refresh_from_db()
        assert wu.num_unsatisfied_requirements == 1
        assert wu.requirements.first() == fetch_url.work_unit

    def _create_pyobject_dist(self) -> Distribution:
        url = "https://files.pythonhosted.org/packages/9e/c5/bcee51324a729c0e46fc6971075f9c931d5600978e0fa860c64e5990a5b8/pyobject-1.2.0.tar.gz#sha256=9d0d5932dec32eb75dd46c66acd2c65acf33f6a3701b2610ba49db8113ca1549"
        WebResource.objects.create(
            url=url,
            freshness=datetime.datetime(2022, 2, 2, 6, 34, 29, 770461, tzinfo=datetime.timezone.utc),
            sha256_hexdigest="9d0d5932dec32eb75dd46c66acd2c65acf33f6a3701b2610ba49db8113ca1549",
            etag='"4fd011a0189718a1d18d4ed0098c9779"',
            content=get_dist_binary_data("pyobject---1.2.0.tar.gz"),
            compression=WebResource.IDENTITY,
        )
        project = Project.get_or_create("pyobject")
        release = Release.get_or_create(project, "1.2.0")
        return Distribution.objects.create(
            release=release,
            filename="pyobject-1.2.0.tar.gz",
            url=url,
            dist_type="SDIST",
            serial_from=12762004,
            serial_to=None,
        )

    def test_process_distribution_non_unicode_modules(self) -> None:
        dist = self._create_pyobject_dist()
        payload = ProcessDistribution.get_or_create(distribution=dist)
        worker = DistributionProcessor()
        assert DistributionData.objects.count() == 0
        assert worker.do_work(payload) is True
        assert DistributionData.objects.count() == 1
        dist_data = DistributionData.objects.first()
        assert dist_data.distribution_id == dist.id
        assert dist_data.distribution == dist
        # Just sampling, tests for data extraction logic are in lang/python
        assert len(dist_data.metadata) == 13
        assert dist_data.metadata["author_email"] == "3416445406@qq.com"
        assert dist_data.metadata["classifiers"] == [
            "Programming Language :: Python",
            "Natural Language :: Chinese (Simplified)",
            "Topic :: Utilities",
            "Topic :: Software Development :: Libraries :: Python Modules",
        ]
        assert dist_data.modules == [
            "pyobject",
            "pyobject.browser",
            "pyobject.code_",
            "pyobject.newtypes",
            "pyobject.search",
            "pyobject.test",
            "pyobject.test.pyc_zipper",
            "pyobject.test.testcode",
        ]
