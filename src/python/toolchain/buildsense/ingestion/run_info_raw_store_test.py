# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import zlib
from io import BytesIO
from pathlib import Path

import boto3
import pytest
from moto import mock_s3

from toolchain.aws.s3 import S3
from toolchain.aws.test_utils.s3_utils import assert_bucket_empty, create_s3_bucket
from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.buildsense.ingestion.run_info_raw_store import RunInfoRawStore, WriteMode
from toolchain.buildsense.records.run_info import RunInfo, ServerInfo
from toolchain.buildsense.test_utils.data_loader import parse_run_info
from toolchain.buildsense.test_utils.fixtures_loader import load_bytes_fixture, load_fixture
from toolchain.django.db.transaction_broker import TransactionBroker
from toolchain.django.site.models import Customer, Repo, ToolchainUser
from toolchain.util.test.util import assert_messages


def store_data(user: ToolchainUser, repo: Repo, build_data: dict) -> None:
    store = RunInfoRawStore.for_repo(repo=repo)
    run_id = build_data["run_info"]["id"]
    store.save_final_build_stats(run_id=run_id, build_stats=build_data, user_api_id=user.api_id)


@pytest.mark.django_db()
class TestRawInfoStore:
    _BUCKET = "fake-test-buildsense-bucket"

    @pytest.fixture()
    def customer(self) -> Customer:
        return Customer.create(slug="kenny", name="acme")

    @pytest.fixture()
    def user(self, customer: Customer) -> ToolchainUser:
        user = ToolchainUser.create(username="kramer", email="kramer@jerrysplace.com")
        customer.add_user(user)
        return user

    @pytest.fixture()
    def repo(self, customer: Customer) -> Repo:
        return Repo.create("ovaltine", customer=customer, name="acmebot")

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_s3():
            create_s3_bucket(self._BUCKET)
            yield

    def _get_fixture(
        self, fixture: str, user: TransactionBroker, repo: Repo, s3_bucket: str | None = None, s3_key="fake-key"
    ) -> tuple[dict, RunInfo]:
        server_info = ServerInfo(
            request_id="test",
            accept_time=utcnow(),
            stats_version="1",
            environment="jambalaya",
            s3_bucket=s3_bucket or self._BUCKET,
            s3_key=s3_key,
        )
        build_data = load_fixture(fixture)
        run_info = parse_run_info(fixture_data=build_data, repo=repo, user=user, server_info=server_info)
        return build_data, run_info

    def test_str(self, repo, user, customer):
        store = RunInfoRawStore.for_repo(repo=repo)
        assert (
            str(store)
            == f"RunInfoRawStore(bucket=fake-test-buildsense-bucket path=no-soup-for-you/buildsense/storage customer_id={customer.pk} repo_id={repo.pk})"
        )

    def _load_json_from_s3(self, key: str) -> dict:
        s3_obj = boto3.resource("s3").Object(self._BUCKET, key).get()
        assert s3_obj["ContentType"] == "application/json"
        return json.loads(s3_obj["Body"].read())

    def test_save_final_build_stats(self, user: ToolchainUser, repo: Repo) -> None:
        build_data, run_info = self._get_fixture("sample4", user, repo)
        store = RunInfoRawStore.for_repo(repo=repo)
        s3_bucket, s3_key = store.save_final_build_stats(
            run_id=run_info.run_id, build_stats=build_data, user_api_id=user.api_id
        )
        assert s3_bucket == "fake-test-buildsense-bucket"
        assert (
            s3_key
            == f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.pk}/{user.api_id}/pants_run_2019_07_19_15_35_18_154_36abaf9ca0894265828d66e1bae1a969/final.json"
        )
        assert build_data == self._load_json_from_s3(s3_key)

    def test_get_build_data(self, user: ToolchainUser, repo: Repo) -> None:
        s3_key = f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.pk}/{user.api_id}/pants_run_2019_07_23_13_27_04_206_2849042e04974d23a1750dc5a290955a/final.json"
        build_data, run_info = self._get_fixture("sample6", user, repo, s3_key=s3_key)
        store_data(user, repo, build_data)
        store = RunInfoRawStore.for_run_info(run_info)
        assert run_info.server_info.s3_key == s3_key  # Sanity check
        assert store.get_build_data(run_info) == build_data
        assert store.named_data_exists(run_info, "final.json") is True

    def test_get_build_data_missing(self, user: ToolchainUser, repo: Repo) -> None:
        s3_key = f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.pk}/{user.api_id}/pants_run_2019_07_23_13_27_04_206_2849042e04974d23a1750dc5a290955a/final.json"
        build_data, run_info = self._get_fixture("sample6", user, repo, s3_key=s3_key)
        store_data(user, repo, build_data)
        store = RunInfoRawStore.for_run_info(run_info)
        assert run_info.server_info.s3_key == s3_key  # Sanity check
        S3().delete_object(bucket=self._BUCKET, key=s3_key)
        with pytest.raises(ToolchainAssertion, match="Missing build file for: run_id"):
            store.get_build_data(run_info)

    def test_load_mismatch(self, user: ToolchainUser, repo: Repo) -> None:
        build_data, run_info = self._get_fixture("sample6", user, repo, s3_key="puffy-shirt")
        store_data(user, repo, build_data)
        store = RunInfoRawStore.for_run_info(run_info)
        with pytest.raises(ToolchainAssertion, match="Mismatch in s3 Bucket/Key."):
            store.get_build_data(run_info)

    def test_save_build_json_file(self, user: ToolchainUser, repo: Repo) -> None:
        store = RunInfoRawStore.for_repo(repo=repo)
        bucket, key = store.save_build_json_file(
            run_id="pants_run_2019_07_23_13_27_04_206_2849042e04974d23a1750dc5a290955a",
            json_bytes_or_file=load_bytes_fixture("sample6.json"),
            name="soup",
            user_api_id=user.api_id,
            mode=WriteMode.OVERWRITE,
            dry_run=False,
            is_compressed=False,
        )

        assert bucket == "fake-test-buildsense-bucket"
        assert (
            key
            == f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.pk}/{user.api_id}/pants_run_2019_07_23_13_27_04_206_2849042e04974d23a1750dc5a290955a/soup.json"
        )
        assert self._load_json_from_s3(key) == load_fixture("sample6")

    def test_get_named_data_missing(self, user: ToolchainUser, repo: Repo) -> None:
        key = f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.pk}/{user.api_id}/pants_run_2020_01_23_11_41_55_931_68189fba67f94d7ebd9b119f4966124c/soup.json"
        build_data, run_info = self._get_fixture("sample_9_end", user, repo, s3_key=key)
        store = RunInfoRawStore.for_repo(repo=repo)
        assert store.get_named_data(run_info=run_info, name="bosco.json") is None
        assert store.get_named_data(run_info=run_info, name="soup.json") is None

    def test_get_named_data(self, user: ToolchainUser, repo: Repo) -> None:
        store = RunInfoRawStore.for_repo(repo=repo)
        bucket, key = store.save_build_json_file(
            run_id="pants_run_2020_01_23_11_41_55_931_68189fba67f94d7ebd9b119f4966124c",
            json_bytes_or_file=load_bytes_fixture("sample_9_end.json"),
            name="ovaltine",
            user_api_id=user.api_id,
            mode=WriteMode.OVERWRITE,
            dry_run=False,
            is_compressed=False,
        )
        assert bucket == "fake-test-buildsense-bucket"
        build_data, run_info = self._get_fixture("sample_9_end", user, repo, s3_key=key)
        content_file = RunInfoRawStore.for_repo(repo=repo).get_named_data(run_info=run_info, name="ovaltine.json")
        assert content_file is not None
        assert content_file.name == "ovaltine.json"
        assert content_file.content_type == "application/json"
        assert content_file.s3_bucket == "fake-test-buildsense-bucket"
        assert (
            content_file.s3_key
            == f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.id}/{user.api_id}/pants_run_2020_01_23_11_41_55_931_68189fba67f94d7ebd9b119f4966124c/ovaltine.json"
        )
        assert not content_file.metadata

        loaded_data = json.loads(content_file.content)
        assert len(loaded_data) == 6
        assert loaded_data == load_fixture("sample_9_end")

    def test_get_named_data_with_metadata(self, user: ToolchainUser, repo: Repo) -> None:
        store = RunInfoRawStore.for_repo(repo=repo)
        bucket, key = store.save_build_file(
            run_id="pants_run_2020_01_23_11_41_55_931_68189fba67f94d7ebd9b119f4966124c",
            content_or_file=b"I refuse to vote. They don't want me I don't want them",
            content_type="text/plain",
            name="elaine",
            user_api_id=user.api_id,
            mode=WriteMode.OVERWRITE,
            dry_run=False,
            metadata={"frank": "constanza", "cosmo": "kramer"},
        )
        assert bucket == "fake-test-buildsense-bucket"
        build_data, run_info = self._get_fixture("sample_9_end", user, repo, s3_key=key)
        content_file = RunInfoRawStore.for_repo(repo=repo).get_named_data(run_info=run_info, name="elaine")
        assert content_file is not None
        assert content_file.content == b"I refuse to vote. They don't want me I don't want them"
        assert content_file.content_type == "text/plain"
        assert content_file.s3_bucket == "fake-test-buildsense-bucket"
        assert (
            content_file.s3_key
            == f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.id}/{user.api_id}/pants_run_2020_01_23_11_41_55_931_68189fba67f94d7ebd9b119f4966124c/elaine"
        )
        assert content_file.metadata == {"frank": "constanza", "cosmo": "kramer"}

    def test_get_named_data_compressed(self, user: ToolchainUser, repo: Repo) -> None:
        key = f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.id}/{user.api_id}/pants_run_2020_01_23_11_41_55_931_68189fba67f94d7ebd9b119f4966124c/elaine"
        store = RunInfoRawStore.for_repo(repo=repo)
        data = BytesIO(zlib.compress(b"I refuse to vote. They don't want me I don't want them." * 3))
        bucket, key = store.save_build_file(
            run_id="pants_run_2020_01_23_11_41_55_931_68189fba67f94d7ebd9b119f4966124c",
            content_or_file=data,
            content_type="text/plain",
            name="elaine",
            user_api_id=user.api_id,
            mode=WriteMode.OVERWRITE,
            dry_run=False,
            metadata={"frank": "constanza"},
            is_compressed=True,
        )
        assert bucket == "fake-test-buildsense-bucket"
        build_data, run_info = self._get_fixture("sample_9_end", user, repo, s3_key=key)
        content_file = RunInfoRawStore.for_repo(repo=repo).get_named_data(run_info=run_info, name="elaine")
        assert content_file is not None
        assert content_file.content == b"I refuse to vote. They don't want me I don't want them." * 3
        assert content_file.content_type == "text/plain"
        assert content_file.s3_bucket == "fake-test-buildsense-bucket"
        assert content_file.s3_key == key
        assert content_file.metadata == {"frank": "constanza", "compression": "zlib"}

    def test_save_text_file(self, user: ToolchainUser, repo: Repo) -> None:
        store = RunInfoRawStore.for_repo(repo=repo)
        bucket, key = store.save_build_file(
            run_id="pants_run_2020_01_23_11_41_55_931_aquarium",
            content_or_file=b"A man carries a wallet",
            content_type="text/plain",
            name="carry-all.txt",
            user_api_id=user.api_id,
            mode=WriteMode.OVERWRITE,
            dry_run=False,
        )
        assert bucket == "fake-test-buildsense-bucket"
        assert (
            key
            == f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.pk}/{user.api_id}/pants_run_2020_01_23_11_41_55_931_aquarium/carry-all.txt"
        )
        s3_obj = boto3.resource("s3").Object("fake-test-buildsense-bucket", key).get()
        assert s3_obj["Body"].read() == b"A man carries a wallet"
        assert s3_obj["ContentType"] == "text/plain"
        assert s3_obj["ContentLength"] == 22
        assert s3_obj["Metadata"] == {}

    def _create_content(self, key: str) -> None:
        S3().upload_content(
            bucket="fake-test-buildsense-bucket",
            key=key,
            content_bytes=b"yo yo ma",
            content_type="text/maestro",
            metadata={"bob": "cobb"},
        )

    def test_save_build_file_with_metadata_overwrite(self, caplog, user: ToolchainUser, repo: Repo) -> None:
        store = RunInfoRawStore.for_repo(repo=repo)
        key = f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.pk}/{user.api_id}/pants_run_2020_01_23_11_41_55_931_aquarium/carry-all.txt"
        self._create_content(key)
        bucket, stored_key = store.save_build_file(
            run_id="pants_run_2020_01_23_11_41_55_931_aquarium",
            content_or_file=b"He is an importer and exporter",
            content_type="text/plain",
            name="carry-all.txt",
            user_api_id=user.api_id,
            mode=WriteMode.OVERWRITE,
            dry_run=False,
            metadata={
                "art": "vandelay",
                "importer": "expoter",
            },
        )
        record = assert_messages(caplog, "save_build_file name='carry-all.txt'")
        assert record is not None
        assert "already exists" not in record.message
        assert bucket == "fake-test-buildsense-bucket"
        assert stored_key == key
        s3_obj = boto3.resource("s3").Object("fake-test-buildsense-bucket", key).get()
        assert s3_obj["Body"].read() == b"He is an importer and exporter"
        assert s3_obj["ContentType"] == "text/plain"
        assert s3_obj["ContentLength"] == 30
        assert s3_obj["Metadata"] == {
            "art": "vandelay",
            "importer": "expoter",
        }

    def test_save_build_file_no_user_api_id(self, caplog, user: ToolchainUser, repo: Repo) -> None:
        store = RunInfoRawStore.for_repo(repo=repo)
        with pytest.raises(ToolchainAssertion, match="User API ID cannot be empty"):
            store.save_build_file(
                run_id="pants_run_2020_01_23_11_41_55_931_aquarium",
                content_or_file=b"He is an importer and exporter",
                content_type="text/plain",
                name="carry-all.txt",
                user_api_id="",
                mode=WriteMode.OVERWRITE,
                dry_run=False,
                metadata={
                    "art": "vandelay",
                    "importer": "expoter",
                },
            )

    def test_save_build_file_invalid_write_mode(self, user: ToolchainUser, repo: Repo) -> None:
        key = f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.pk}/{user.api_id}/pants_run_2020_01_23_11_41_55_931_aquarium/davola.txt"
        self._create_content(key)
        store = RunInfoRawStore.for_repo(repo=repo)
        with pytest.raises(ToolchainAssertion, match="Invalid WriteMode: PeZ"):
            store.save_build_file(
                run_id="pants_run_2020_01_23_11_41_55_931_aquarium",
                content_or_file=b"He is an importer and exporter",
                content_type="text/plain",
                name="davola.txt",
                user_api_id=user.api_id,
                mode="PeZ",  # type: ignore[arg-type]
                dry_run=False,
            )

    def test_save_build_file_skip_existing(self, caplog, user: ToolchainUser, repo: Repo) -> None:
        key = f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.pk}/{user.api_id}/pants_run_2020_01_23_11_41_55_931_aquarium/carry-all.txt"
        S3().upload_content(
            bucket="fake-test-buildsense-bucket",
            key=key,
            content_bytes=b"yo yo ma",
            content_type="text/kramer",
            metadata={"art": "vandelay"},
        )
        store = RunInfoRawStore.for_repo(repo=repo)
        bucket, stored_key = store.save_build_file(
            run_id="pants_run_2020_01_23_11_41_55_931_aquarium",
            content_or_file=b"He is an importer and exporter",
            content_type="text/plain",
            name="carry-all.txt",
            user_api_id=user.api_id,
            mode=WriteMode.SKIP,
            dry_run=False,
            metadata={
                "importer": "expoter",
            },
        )
        assert_messages(caplog, "save_build_file already exists key=")
        assert bucket == "fake-test-buildsense-bucket"
        assert stored_key == key
        s3_obj = boto3.resource("s3").Object("fake-test-buildsense-bucket", key).get()
        assert s3_obj["Body"].read() == b"yo yo ma"
        assert s3_obj["ContentType"] == "text/kramer"
        assert s3_obj["ContentLength"] == 8
        assert s3_obj["Metadata"] == {
            "art": "vandelay",
        }

    def _prep_build_data(self, repo: Repo, user: ToolchainUser, run_id: str) -> tuple[str, RunInfo]:
        key_base = f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.pk}/{user.api_id}/{run_id}"
        build_stats, run_info = self._get_fixture("sample_9_end", user, repo, s3_key=f"{key_base}/final.json")
        run_info.run_id = run_id
        store = RunInfoRawStore.for_repo(repo=repo)
        store.save_final_build_stats(run_id=run_id, build_stats=build_stats, user_api_id=user.api_id)
        key = f"{key_base}/medium-rare.json"
        S3().upload_content(self._BUCKET, key, content_bytes=b'{"low": "flow}', content_type="application/json")
        return key, run_info

    def test_delete_named_data(self, user: ToolchainUser, repo: Repo) -> None:
        key, run_info = self._prep_build_data(
            repo, user, run_id="pants_run_2020_01_23_11_41_55_931_68189fba67f94d7ebd9b119f4966124c"
        )
        s3 = S3()
        assert s3.exists("fake-test-buildsense-bucket", key) is True
        store = RunInfoRawStore.for_repo(repo=repo)
        store.delete_named_data(run_info, "medium-rare.json")
        assert s3.exists("fake-test-buildsense-bucket", key) is False

    def test_named_data_exists(self, user: ToolchainUser, repo: Repo) -> None:
        s3_key = f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.pk}/{user.api_id}/pants_run_2019_07_23_13_27_04_206_2849042e04974d23a1750dc5a290955a/final.json"
        build_data, run_info = self._get_fixture("sample6", user, repo, s3_key=s3_key)
        store_data(user, repo, build_data)
        store = RunInfoRawStore.for_run_info(run_info)
        assert store.named_data_exists(run_info, "pez") is False

    def test_delete_build_data(self, user: ToolchainUser, repo: Repo) -> None:
        _, run_info = self._prep_build_data(repo, user, run_id="pants_run_2020_01_23_11_41_55_931_68189fba67f94d7c")
        store = RunInfoRawStore.for_repo(repo=repo)
        assert store.delete_build_data(run_info=run_info, dry_run=False) == 2
        assert_bucket_empty(S3(), self._BUCKET)

    def test_delete_build_data_dry_run(self, user: ToolchainUser, repo: Repo) -> None:
        key, run_info = self._prep_build_data(repo, user, run_id="pants_run_2020_01_23_11_41_55_931_68189fba67f94d7c")
        store = RunInfoRawStore.for_repo(repo=repo)
        assert store.delete_build_data(run_info=run_info, dry_run=True) == 2
        s3 = S3()
        assert s3.exists("fake-test-buildsense-bucket", key) is True
        assert s3.exists("fake-test-buildsense-bucket", run_info.server_info.s3_key) is True

    def test_delete_build_data_unexpected_run_id(self, user: ToolchainUser, repo: Repo) -> None:
        key, run_info = self._prep_build_data(repo, user, run_id="jerry_2020_01_23_11_41_55_931_68189fba67f94d7c")
        store = RunInfoRawStore.for_repo(repo=repo)
        with pytest.raises(ToolchainAssertion, match="Unexpected s3 key in delete_build_data"):
            store.delete_build_data(run_info=run_info, dry_run=False)
        s3 = S3()
        assert s3.exists("fake-test-buildsense-bucket", key) is True
        assert s3.exists("fake-test-buildsense-bucket", run_info.server_info.s3_key) is True

    def test_delete_build_data_max_files_exceeded(self, user: ToolchainUser, repo: Repo) -> None:
        main_key, run_info = self._prep_build_data(repo, user, run_id="pants_run_2020_01_23_11_41_55_931_68189c")
        key_base = Path(main_key).parent
        s3 = S3()
        for i in range(50):
            key = (key_base / f"jerry_{i}.json").as_posix()
            s3.upload_content(self._BUCKET, key, content_bytes=f"poise counts! {i}".encode(), content_type="text/plain")
        store = RunInfoRawStore.for_repo(repo=repo)
        with pytest.raises(ToolchainAssertion, match="Unexpected number of keys under"):
            store.delete_build_data(run_info=run_info, dry_run=False)

    def test_delete_build_data_legacy_fromat(self, user: ToolchainUser, repo: Repo) -> None:
        run_id = "pants_run_2020_01_10_15_11_07_34_319ea3c64bbc49a09d2ef4fbd0d5945f"
        s3_key = f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.pk}/{user.api_id}/{run_id}"
        build_stats, run_info = self._get_fixture("sample_9_end", user, repo, s3_key=s3_key)
        run_info.run_id = run_id
        S3().upload_content(
            self._BUCKET, s3_key, content_bytes=json.dumps(build_stats).encode(), content_type="application/json"
        )
        store = RunInfoRawStore.for_repo(repo=repo)
        assert store.delete_build_data(run_info=run_info, dry_run=False) == 1
        assert_bucket_empty(S3(), self._BUCKET)
