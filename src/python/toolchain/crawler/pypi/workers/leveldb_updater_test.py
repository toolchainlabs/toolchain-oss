# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import gzip
import json
from pathlib import Path

import pytest
from moto import mock_s3

from toolchain.aws.s3 import S3
from toolchain.aws.test_utils.s3_utils import create_s3_bucket
from toolchain.crawler.pypi.models import UpdateLevelDb
from toolchain.crawler.pypi.workers.leveldb_updater import LevelDbUpdater
from toolchain.satresolver.pypi.depgraph import Depgraph
from toolchain.satresolver.pypi.python_distribution import PythonPackageDistribution
from toolchain.satresolver.test_helpers.pypi_test_data import DistributionsSet
from toolchain.satresolver.test_helpers.pypi_utils import create_fake_depgraph

_DIST_DATA = {
    # The "format/order" of the dumped dist data is based on DistributionData.get_data_shard
    # See the list of fields passed to qs.values_list(....)
    "quasinet": [
        "quasinet-0.0.34.tar.gz",
        "quasinet",
        "0.0.34",
        "SDIST",
        "ae105e994438b045ca88732580619c61419bbdba721fe1735c25509319dc2022",
        None,
        [
            "numpy (>=1.6)",
            "pandas (>=0.22.0)",
            "matplotlib (>=2.0.2)",
            "rpy2 (==2.8.6)",
            "scipy (>=1.1.0)",
            "ascii-graph (>=1.5.1)",
            "graphviz (>=0.10.1)",
            "networkx (>=2.2)",
            "scikit-learn (>=0.20.3)",
            "pygraphviz (>=1.5)",
        ],
        "==2.7.*",
        ["quasinet", "quasinet.Qnet", "quasinet.mlx"],
    ],
    "zensols": [
        "zensols.actioncli-1.1.1-py3.7.egg",
        "zensols.actioncli",
        "1.1.1",
        "BDIST",
        "247487a54def887d1b64a0036da94f656385d86074d2275f3c48df0b87fec5e3",
        None,
        None,
        None,
        [
            "zensols.actioncli",
            "zensols.actioncli.config",
            "zensols.actioncli.executor",
            "zensols.actioncli.factory",
            "zensols.actioncli.yaml_config",
        ],
    ],
    "oncall": [
        "oncall-slackbot-1.1.0.tar.gz",
        "oncall-slackbot",
        "1.1.0",
        "SDIST",
        "d67ee17545510683423fdeb4fccac61f0f8e4f362663b05f75a58dbd088432aa",
        None,
        ["slackbot (==0.5.5)", "pygerduty (>=0.38.2)", "pytz (>=2019.3)", "humanize (>=0.5.1)", "spacy (==2.2.3)"],
        None,
        [
            "oncall_slackbot",
            "oncall_slackbot.bot",
            "oncall_slackbot.dispatcher",
            "oncall_slackbot.integrations.pagerduty",
            "oncall_slackbot.plugins",
            "oncall_slackbot.plugins.oncall",
            "oncall_slackbot.settings",
            "oncall_slackbot.slackclient",
            "slacker_blocks",
        ],
    ],
    "twine-bad": [
        "twine-1.1.0-py2.py3-none-any.whl",
        "twine",
        "1.1.0",
        "WHEEL",
        "9a9aff6377e66f5fed197910a6d2bd4e34f20f1e584733ed3e3a4b8ed94cb89c",
        None,
        ["six", "requests", "pkginfo", "argparse; python_version == 2.6"],
        None,
        [
            "twine",
            "twine.application",
            "twine.commands",
            "twine.commands.upload",
            "twine.exceptions",
            "twine.utils",
            "twine.wheel",
        ],
    ],
    "python-otcclient-bad": [
        "python_otcclient-0.2.7-py2.py3-none-any.whl",
        "python-otcclient",
        "0.2.7",
        "WHEEL",
        "9659bf3e0fd13b9ea8cc67e8e6d48b6472e9a642527e6fec5a2d0d0e5886c5ab",
        None,
        ["boto3>=1.3.0", "prettytable>=0.7.0", "requests>=2.10.0", "jmespath>=0.7.1,<1.0.0", "#objectpath>=0.5"],
        None,
        [
            "otcclient",
            "otcclient.core",
            "otcclient.core.OtcConfig",
            "otcclient.core.argmanager",
            "otcclient.utils.utils_output",
            "otcclient.utils.utils_s3",
            "otcclient.utils.utils_singleton",
        ],
    ],
}


@pytest.mark.django_db()
class TestLevelDbUpdater:
    _BUCKET = "jambalaya.ap-northeast-1.toolchain.com"

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_s3():
            create_s3_bucket(self._BUCKET)
            yield

    def _create_local_leveldb(self, tmp_path: Path, dists) -> str:
        db_path = tmp_path / "leveldbs" / "07762"
        db_path.mkdir(parents=True)
        create_fake_depgraph(db_path, *dists)
        return f"file://{db_path}/"

    def _create_dumped_data(self, s3: S3, *packages: str) -> None:
        dumped_data = [_DIST_DATA[pkg] for pkg in packages]
        content = gzip.compress(json.dumps(dumped_data).encode())
        s3.upload_content(bucket=self._BUCKET, key="dumped_data/soup.zip", content_bytes=content)

    def _assert_dist(self, depgraph: Depgraph, name: str, version: str) -> PythonPackageDistribution:
        dists = list(depgraph.get_distributions(name, version=version))
        assert len(dists) == 1
        dist = dists[0]
        assert dist.subject == dist.package_name == name
        assert dist.version == version
        return dist

    def test_create_depgraph_from_scratch(self) -> None:
        s3 = S3(region="ap-northeast-1")
        self._create_dumped_data(s3, "zensols", "quasinet")
        payload = UpdateLevelDb.create(
            input_dir_url=f"s3://{self._BUCKET}/dumped_data/",
            output_dir_url=f"s3://{self._BUCKET}/depgraph/leveldbs/03700/",
            existing_leveldb_dir_url=None,
            builder_cls="DepgraphBuilder",
        )
        worker = LevelDbUpdater()
        assert worker.do_work(payload) is True
        assert s3.exists(bucket=self._BUCKET, key="depgraph/input_lists/03700") is True
        depgraph = Depgraph.from_url(f"s3://{self._BUCKET}/depgraph/leveldbs/03700/")
        dist = self._assert_dist(depgraph, name="quasinet", version="0.0.34")
        assert dist.platform == ""
        assert dist.requires_python == "==2.7.*"
        assert dist.requires == (
            "numpy (>=1.6)",
            "pandas (>=0.22.0)",
            "matplotlib (>=2.0.2)",
            "rpy2 (==2.8.6)",
            "scipy (>=1.1.0)",
            "ascii-graph (>=1.5.1)",
            "graphviz (>=0.10.1)",
            "networkx (>=2.2)",
            "scikit-learn (>=0.20.3)",
            "pygraphviz (>=1.5)",
        )

    def test_create_depgraph_from_incremental_without_input_files(self, tmp_path: Path) -> None:
        s3 = S3(region="ap-northeast-1")
        self._create_dumped_data(s3, "zensols", "oncall")
        local_leveldb = self._create_local_leveldb(tmp_path, DistributionsSet.dist_set_2)
        payload = UpdateLevelDb.create(
            input_dir_url=f"s3://{self._BUCKET}/dumped_data/",
            output_dir_url=f"s3://{self._BUCKET}/depgraph/leveldbs/03700/",
            existing_leveldb_dir_url=local_leveldb,
            builder_cls="DepgraphBuilder",
        )
        worker = LevelDbUpdater()
        assert worker.do_work(payload) is True
        assert s3.exists(bucket=self._BUCKET, key="depgraph/input_lists/03700") is True
        depgraph = Depgraph.from_url(f"s3://{self._BUCKET}/depgraph/leveldbs/03700/")
        # From existing leveldb
        dist = self._assert_dist(depgraph, name="aaa", version="1.0.0")
        assert dist.platform == "any"
        assert dist.requires_python == "python==2.7.6"
        assert dist.requires == ()

        # from new dist data
        dist = self._assert_dist(depgraph, name="oncall-slackbot", version="1.1.0")
        assert dist.platform == ""
        assert dist.requires_python == ""
        assert dist.requires == (
            "slackbot (==0.5.5)",
            "pygerduty (>=0.38.2)",
            "pytz (>=2019.3)",
            "humanize (>=0.5.1)",
            "spacy (==2.2.3)",
        )

    def test_create_depgraph_with_bad_reqs(self) -> None:
        s3 = S3(region="ap-northeast-1")
        self._create_dumped_data(s3, "oncall", "twine-bad", "quasinet")
        payload = UpdateLevelDb.create(
            input_dir_url=f"s3://{self._BUCKET}/dumped_data/",
            output_dir_url=f"s3://{self._BUCKET}/depgraph/leveldbs/03700/",
            existing_leveldb_dir_url=None,
            builder_cls="DepgraphBuilder",
        )
        worker = LevelDbUpdater()
        assert worker.do_work(payload) is True
        assert s3.exists(bucket=self._BUCKET, key="depgraph/input_lists/03700") is True
        depgraph = Depgraph.from_url(f"s3://{self._BUCKET}/depgraph/leveldbs/03700/")
        dist = self._assert_dist(depgraph, name="twine", version="1.1.0")
        assert dist.platform == "any"
        assert dist.requires_python == ">=2,<4"
        assert dist.requires == ("six", "requests", "pkginfo")

    def test_create_depgraph_with_commened_out_reqs(self) -> None:
        s3 = S3(region="ap-northeast-1")
        self._create_dumped_data(s3, "python-otcclient-bad", "oncall", "quasinet")
        payload = UpdateLevelDb.create(
            input_dir_url=f"s3://{self._BUCKET}/dumped_data/",
            output_dir_url=f"s3://{self._BUCKET}/depgraph/leveldbs/03700/",
            existing_leveldb_dir_url=None,
            builder_cls="DepgraphBuilder",
        )
        worker = LevelDbUpdater()
        assert worker.do_work(payload) is True
        assert s3.exists(bucket=self._BUCKET, key="depgraph/input_lists/03700") is True
        depgraph = Depgraph.from_url(f"s3://{self._BUCKET}/depgraph/leveldbs/03700/")
        dist = self._assert_dist(depgraph, name="python-otcclient", version="0.2.7")
        assert dist.platform == "any"
        assert dist.requires_python == ">=2,<4"
        assert dist.requires == ("boto3>=1.3.0", "prettytable>=0.7.0", "requests>=2.10.0", "jmespath>=0.7.1,<1.0.0")
