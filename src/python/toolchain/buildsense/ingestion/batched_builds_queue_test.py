# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
import zlib
from io import BytesIO
from pathlib import PurePath

import boto3
import pytest
from django.core.files.uploadedfile import InMemoryUploadedFile
from moto import mock_s3

from toolchain.aws.s3 import S3
from toolchain.aws.test_utils.s3_utils import create_s3_bucket
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.buildsense.ingestion.batched_builds_queue import BatchedBuildsQueue, JsonBuildStats
from toolchain.buildsense.test_utils.fixtures_loader import load_fixture
from toolchain.django.site.models import Customer, Repo, ToolchainUser


@pytest.mark.django_db()
class TestBatchedBuildsQueue:
    _BUCKET = "fake-test-buildsense-bucket"

    @pytest.fixture(autouse=True)
    def _disable_real_aws(self, monkeypatch):
        monkeypatch.setenv("K8S_POD_NAME", "enigma")

    @pytest.fixture()
    def customer(self) -> Customer:
        return Customer.create(slug="tinsel", name="Festivus For the rest of us")

    @pytest.fixture()
    def user(self, customer: Customer) -> ToolchainUser:
        user = ToolchainUser.create(username="nobagel", email="nobagel@pole.com")
        customer.add_user(user)
        return user

    @pytest.fixture()
    def repo(self, customer: Customer) -> Repo:
        return Repo.create("ovaltine", customer=customer, name="Gold Jerry! Gold!")

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_s3():
            create_s3_bucket(self._BUCKET)
            yield

    def _load_fixtures(self, *fixtures: str) -> JsonBuildStats:
        data = {}
        for fixture_name in fixtures:
            build_stats = load_fixture(fixture_name)
            run_id = build_stats["run_info"]["id"]
            data[run_id] = build_stats
        return data

    def _load_json_from_s3(self, key: str, new_format: bool) -> tuple[dict, dict]:
        s3_obj = boto3.resource("s3").Object(self._BUCKET, key).get()
        assert s3_obj["ContentType"] == "application/json"
        metadata = s3_obj["Metadata"]
        content = s3_obj["Body"].read()
        data = zlib.decompress(content) if new_format else content
        return json.loads(data), metadata

    def _queue_builds(self, repo: Repo, user: ToolchainUser, *fixtures: str) -> str:
        builds = self._load_fixtures(*fixtures)
        accepted_time = datetime.datetime(2020, 3, 19, 17, 38, 51, tzinfo=datetime.timezone.utc)
        metadata = {
            "customer_id": repo.customer_id,
            "repo_id": repo.id,
            "user_api_id": user.api_id,
            "accepted_time": datetime.datetime(2020, 3, 19, 17, 38, 51, tzinfo=datetime.timezone.utc).isoformat(),
            "node_id": "soup",
            "request_id": "butter-bean",
            "compress": "zlib",
        }
        time_str = accepted_time.strftime("%Y_%m_%d_%H_%M_%S")
        key_path = PurePath("bad-chicken/mess-u-up") / "builds" / repo.customer_id / repo.id / f"{time_str}_jerry.json"
        fp = BytesIO(zlib.compress(json.dumps(builds).encode()))
        S3().upload_fileobj(
            bucket=self._BUCKET, key=key_path.as_posix(), fp=fp, content_type="application/json", metadata=metadata
        )
        return key_path.as_posix()

    def test_queue_builds_dict(self, repo: Repo, user: ToolchainUser) -> None:
        builds_queue = BatchedBuildsQueue.for_repo(repo)

        builds = self._load_fixtures("sample_10_finish", "sample_9_end", "ci_build_pr_final_1")
        accepted_time = datetime.datetime(2020, 3, 19, 17, 38, 51, tzinfo=datetime.timezone.utc)
        bucket, key = builds_queue.queue_builds(
            builds, user_api_id=user.api_id, accepted_time=accepted_time, request_id="butter-bean"
        )
        assert bucket == "fake-test-buildsense-bucket"
        assert key == f"bad-chicken/mess-u-up/builds/{repo.customer_id}/{repo.id}/2020_03_19_17_38_51_enigma.json"
        queued_builds, metadata = self._load_json_from_s3(
            f"bad-chicken/mess-u-up/builds/{repo.customer_id}/{repo.id}/2020_03_19_17_38_51_enigma.json",
            new_format=True,
        )
        assert queued_builds == self._load_fixtures("sample_10_finish", "sample_9_end", "ci_build_pr_final_1")
        assert metadata == {
            "customer_id": repo.customer_id,
            "repo_id": repo.id,
            "user_api_id": user.api_id,
            "accepted_time": "2020-03-19T17:38:51+00:00",
            "node_id": "enigma",
            "request_id": "butter-bean",
            "compression": "zlib",
        }

    def test_queue_builds_django_file(self, repo: Repo, user: ToolchainUser) -> None:
        builds_queue = BatchedBuildsQueue.for_repo(repo)
        builds = self._load_fixtures("sample_10_finish", "sample_9_end", "ci_build_pr_final_1")
        data = zlib.compress(json.dumps(builds).encode())
        django_file = InMemoryUploadedFile(
            file=BytesIO(data),
            field_name="pole",
            name="soup.bin",
            content_type="application/json",
            size=len(data),
            charset=None,
        )
        accepted_time = datetime.datetime(2020, 3, 19, 17, 38, 51, tzinfo=datetime.timezone.utc)
        bucket, key = builds_queue.queue_builds(
            django_file, user_api_id=user.api_id, accepted_time=accepted_time, request_id="butter-bean"
        )
        assert bucket == "fake-test-buildsense-bucket"
        assert key == f"bad-chicken/mess-u-up/builds/{repo.customer_id}/{repo.id}/2020_03_19_17_38_51_enigma.json"
        queued_builds, metadata = self._load_json_from_s3(
            f"bad-chicken/mess-u-up/builds/{repo.customer_id}/{repo.id}/2020_03_19_17_38_51_enigma.json",
            new_format=True,
        )
        assert queued_builds == self._load_fixtures("sample_10_finish", "sample_9_end", "ci_build_pr_final_1")
        assert metadata == {
            "customer_id": repo.customer_id,
            "repo_id": repo.id,
            "user_api_id": user.api_id,
            "accepted_time": "2020-03-19T17:38:51+00:00",
            "node_id": "enigma",
            "request_id": "butter-bean",
            "compression": "zlib",
        }

    def test_get_builds_invalid_path(self, repo: Repo) -> None:
        queue = BatchedBuildsQueue.for_repo(repo)
        with pytest.raises(
            ToolchainAssertion, match="Unexpected s3_key='caffe-latte/sip' base_path='bad-chicken/mess-u-up'"
        ):
            queue.get_builds("caffe-latte/sip")

    def test_get_builds_old(self, repo: Repo, user: ToolchainUser) -> None:
        key = f"bad-chicken/mess-u-up/builds/{repo.customer_id}/{repo.id}/2020_03_19_17_38_51_enigma.json"
        data = {
            "customer_id": repo.customer_id,
            "repo_id": repo.id,
            "user_api_id": user.api_id,
            "accepted_time": datetime.datetime(2020, 3, 19, 17, 38, 51, tzinfo=datetime.timezone.utc).isoformat(),
            "node_id": "soup",
            "request_id": "jambalaya",
            "builds": self._load_fixtures("sample7", "sample_9_end"),
        }
        S3().upload_json_str(self._BUCKET, key, json_str=json.dumps(data))
        builds_data = BatchedBuildsQueue.for_repo(repo).get_builds(key)
        assert builds_data.accepted_time == datetime.datetime(2020, 3, 19, 17, 38, 51, tzinfo=datetime.timezone.utc)
        assert builds_data.customer_id == repo.customer_id
        assert builds_data.repo_id == repo.id
        assert builds_data.user_api_id == user.api_id
        assert builds_data.request_id == "jambalaya"
        assert len(builds_data.builds) == 2
        sample7 = builds_data.builds["pants_run_2019_08_21_14_10_19_355_32e8c441686b4205ba2668842e363922"]
        sample9 = builds_data.builds["pants_run_2020_01_23_11_41_55_931_68189fba67f94d7ebd9b119f4966124c"]
        assert sample9["run_info"]["datetime"] == "Thursday Jan 23, 2020 11:41:55"
        assert sample7["run_info"]["revision"] == "5ecd85cb10699ee6f396c64aaaf12ca9b788fa48"

    def test_get_builds_new(self, repo: Repo, user: ToolchainUser) -> None:
        key = self._queue_builds(repo, user, "sample7", "sample_9_end")
        builds_data = BatchedBuildsQueue.for_repo(repo).get_builds(key)
        assert builds_data.customer_id == repo.customer_id
        assert builds_data.repo_id == repo.id
        assert builds_data.user_api_id == user.api_id
        assert builds_data.request_id == "butter-bean"
        assert len(builds_data.builds) == 2
        sample7 = builds_data.builds["pants_run_2019_08_21_14_10_19_355_32e8c441686b4205ba2668842e363922"]
        sample9 = builds_data.builds["pants_run_2020_01_23_11_41_55_931_68189fba67f94d7ebd9b119f4966124c"]
        assert sample9["run_info"]["datetime"] == "Thursday Jan 23, 2020 11:41:55"
        assert sample7["run_info"]["revision"] == "5ecd85cb10699ee6f396c64aaaf12ca9b788fa48"

    def test_str(self, repo: Repo) -> None:
        bq = BatchedBuildsQueue.for_repo(repo)
        assert str(bq).startswith("BatchedBuildsQueue(bucket=fake-test-buildsense-bucket path")
