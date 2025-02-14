# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime

import pytest

from toolchain.base.datetime_tools import utcnow
from toolchain.django.webresource.models import WebResource
from toolchain.packagerepo.pypi.models import Distribution, DistributionData, Project, Release


@pytest.mark.django_db()
class TestDistributionData:
    def _create_dist_objects(self) -> Distribution:
        project = Project.get_or_create("databricks-connect")
        release = Release.get_or_create(project, "6.3.1")
        dist_dict = {
            "filename": "databricks-connect-6.3.1.tar.gz",
            "dist_type": "SDIST",
            "url": "https://jerry.com/databricks-connect-6.3.1.tar.gz",
            "digests": {"sha256": "no-soup-for-you"},
        }
        return Distribution.get_or_create_from_dict(dist_dict, release, serial_from=300)

    def _create_web_resource(self, distribution: Distribution) -> WebResource:
        return WebResource.objects.create(
            url=distribution.url,
            sha256_hexdigest="no-soup-for-you",
            freshness=utcnow() - datetime.timedelta(days=20),
            encoding="",
            compression=WebResource.IDENTITY,
            content_url="s3://jambalaya/no-soup-for-you/databricks.dist",
            etag='"c70fcaa4abba16c1874c65a643e525f9"',
        )

    def test_create(self) -> None:
        dist = self._create_dist_objects()
        web_resource = self._create_web_resource(dist)
        dist_data = DistributionData.update_or_create(
            dist,
            web_resource,
            metadata={"author": "Databricks", "provides_extras": ["ml", "mllib", "sql"]},
            modules=["pyspark", "pyspark.accumulators"],
        )
        assert dist_data.distribution_id == dist.id
        assert dist_data.web_resource.id == web_resource.id
        assert dist_data.metadata == {"author": "Databricks", "provides_extras": ["ml", "mllib", "sql"]}
        assert dist_data.modules == ["pyspark", "pyspark.accumulators"]

    def test_get_data_shard(self) -> None:
        dist = self._create_dist_objects()
        web_resource = self._create_web_resource(dist)
        DistributionData.update_or_create(
            dist,
            web_resource,
            metadata={"author": "Databricks", "provides_extras": ["ml", "mllib", "sql"]},
            modules=["pyspark", "pyspark.accumulators"],
        )
        shard = DistributionData.get_data_shard(shard=0, num_shards=1, serial_from=250, serial_to=350)
        assert shard == [
            (
                "databricks-connect-6.3.1.tar.gz",
                "databricks-connect",
                "6.3.1",
                "SDIST",
                "no-soup-for-you",
                None,
                None,
                None,
                ["pyspark", "pyspark.accumulators"],
            )
        ]
