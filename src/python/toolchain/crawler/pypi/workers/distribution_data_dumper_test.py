# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime
import gzip
import json

import pytest
from moto import mock_s3

from toolchain.aws.s3 import S3
from toolchain.aws.test_utils.s3_utils import create_s3_bucket
from toolchain.base.datetime_tools import utcnow
from toolchain.crawler.pypi.models import DumpDistributionData
from toolchain.crawler.pypi.workers.distribution_data_dumper import DistributionDataDumper
from toolchain.django.webresource.models import WebResource
from toolchain.packagerepo.pypi.models import Distribution, DistributionData, Project, Release


@pytest.mark.django_db()
class TestDistributionDataDumper:
    @pytest.fixture(autouse=True)
    def _start_moto(self, settings):
        with mock_s3():
            create_s3_bucket(settings.WEBRESOURCE_BUCKET)
            yield

    def _create_dist_objects(self):
        project = Project.get_or_create("databricks-connect")
        release = Release.get_or_create(project, "6.3.1")
        dist_dict = {
            "filename": "databricks-connect-6.3.1.tar.gz",
            "dist_type": "SDIST",
            "url": "https://jerry.com/databricks-connect-6.3.1.tar.gz",
            "digests": {"sha256": "no-soup-for-you"},
        }
        distribution = Distribution.get_or_create_from_dict(dist_dict, release, serial_from=300)
        web_resource = WebResource.objects.create(
            url=distribution.url,
            sha256_hexdigest="no-soup-for-you",
            freshness=utcnow() - datetime.timedelta(days=20),
            encoding="",
            compression=WebResource.IDENTITY,
            content_url="s3://jambalaya/no-soup-for-you/databricks.dist",
            etag='"c70fcaa4abba16c1874c65a643e525f9"',
        )
        DistributionData.update_or_create(
            distribution,
            web_resource,
            metadata={
                "author": "Databricks",
                "provides_extras": ["ml", "mllib", "sql"],
                "requires_python": ">=2.7",
                "requires": ["six"],
            },
            modules=["pyspark", "pyspark.accumulators"],
        )

    def test_dump_distribution(self) -> None:
        self._create_dist_objects()
        payload = DumpDistributionData.trigger_incremental(serial_from=290, serial_to=301)
        worker = DistributionDataDumper()
        assert worker.do_work(payload) is True
        content = S3().get_content(
            bucket="jambalaya",
            key="seinfeld/no-soup-for-you/data_dumps/python_distribution_data/290-301/python_distribution_data0000.json.gz",
        )
        assert len(content) == 136
        dist_data = json.loads(gzip.decompress(content))
        assert len(dist_data) == 1
        assert dist_data[0] == [
            "databricks-connect-6.3.1.tar.gz",
            "databricks-connect",
            "6.3.1",
            "SDIST",
            "no-soup-for-you",
            ["six"],
            None,
            ">=2.7",
            ["pyspark", "pyspark.accumulators"],
        ]
