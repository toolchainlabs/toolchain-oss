# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
import sqlite3
import zlib
from collections.abc import Sequence
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import boto3
import botocore
import httpx
import pytest
from django.http import HttpResponse
from moto import mock_dynamodb, mock_s3
from rest_framework.test import APIClient

from toolchain.aws.s3 import S3
from toolchain.aws.test_utils.s3_utils import create_s3_bucket
from toolchain.bitbucket_integration.client.repo_clients_test import (
    add_bitbucket_pr_response_for_repo,
    add_bitbucket_push_response_for_repo,
)
from toolchain.buildsense.ingestion.models import ProcessPantsRun, ProcessQueuedBuilds
from toolchain.buildsense.ingestion.run_info_table import RunInfoTable
from toolchain.buildsense.records.run_info import RunInfo
from toolchain.buildsense.test_utils.fixtures_loader import load_bytes_fixture, load_fixture
from toolchain.buildsense.test_utils.table_utils import get_table_items_count
from toolchain.django.auth.claims import RepoClaims
from toolchain.django.auth.constants import AccessTokenAudience, AccessTokenType
from toolchain.django.auth.utils import create_internal_auth_headers
from toolchain.django.site.models import Customer, Repo, ToolchainUser
from toolchain.django.site.test_helpers.models_helpers import create_bitbucket_user, create_github_user, create_staff
from toolchain.github_integration.client.repo_clients_test import (
    add_github_pr_response_for_repo,
    add_github_push_response_for_repo,
    add_pr_response_exception_for_repo,
)
from toolchain.users.client.user_client import UserClient
from toolchain.users.client.user_client_test import add_resolve_user_response, add_resolve_user_response_fail
from toolchain.util.test.util import convert_headers_to_wsgi


@dataclass(frozen=True)
class ClientConfig:
    use_compression: bool
    use_file_upload: bool

    @classmethod
    def default(cls) -> ClientConfig:
        return cls(use_compression=False, use_file_upload=False)


def _get_headers_for_client(user: ToolchainUser, claims: RepoClaims) -> dict[str, str]:
    headers = create_internal_auth_headers(user, claims=claims.as_json_dict(), impersonation=None)
    return convert_headers_to_wsgi(headers)


class CompressibleAPIClient(APIClient):
    def __init__(self, cfg: ClientConfig, user_agent: str, enforce_csrf_checks=False, **defaults):
        super().__init__(
            enforce_csrf_checks=enforce_csrf_checks,
            HTTP_X_FORWARDED_FOR="35.175.222.211, 10.1.116.159, 127.0.0.1, 10.1.100.87",
            HTTP_USER_AGENT=user_agent,
            **defaults,
        )
        self._cfg = cfg

    def _encode_data(self, data, format=None, content_type=None):
        if format == "toolchain_json_data":
            return super()._encode_data(data=json.dumps(data), format=None, content_type="application/json")
        return super()._encode_data(data=data, format=format, content_type=content_type)

    def generic(self, method, path, data="", content_type="application/octet-stream", secure=False, **extra):
        if method in {"POST", "PATCH"} and self._cfg.use_compression:
            data = zlib.compress(data)
            extra = dict(extra)
            extra["HTTP_CONTENT_ENCODING"] = "compress"
        return super().generic(method, path, data, content_type, **extra)


def _get_client(user_agent: str, extra_headers: dict[str, str]) -> APIClient:
    return CompressibleAPIClient(cfg=ClientConfig.default(), user_agent=user_agent, **extra_headers)


def _get_client_for_user(user: ToolchainUser, claims: RepoClaims) -> APIClient:
    return _get_client(
        user_agent="pants/v2.9.0rc0+gita0a1a7d5 toolchain/v0.16.0",
        extra_headers=_get_headers_for_client(user, claims),
    )


def create_github_user_and_response(
    httpx_mock, customer: Customer, username: str, github_user_id: str, github_username: str
):
    user = create_github_user(username=username, github_username=github_username, github_user_id=github_user_id)
    add_resolve_user_response(
        httpx_mock,
        user=user,
        customer_id=customer.id,
        scm_user_id=github_user_id,
        scm_username=github_username,
        scm_provider=UserClient.Auth.GITHUB,
    )
    return user


def create_bitbucket_user_and_response(
    httpx_mock, customer: Customer, username: str, bitbucket_user_id: str, bitbucket_username: str
):
    user = create_bitbucket_user(
        username=username, bitbucket_user_id=bitbucket_user_id, bitbucket_username=bitbucket_username
    )
    add_resolve_user_response(
        httpx_mock,
        user=user,
        customer_id=customer.id,
        scm_user_id=bitbucket_user_id,
        scm_username=bitbucket_username,
        scm_provider=UserClient.Auth.BITBUCKET,
    )
    return user


@pytest.mark.django_db()
class BaseViewsApiTest:
    _BUCKET = "fake-test-buildsense-bucket"

    @pytest.fixture()
    def customer(self) -> Customer:
        return Customer.create(slug="acmeid", name="acme")

    @pytest.fixture()
    def user(self, customer: Customer) -> ToolchainUser:
        user = ToolchainUser.create(username="kramer", email="kramer@jerrysplace.com")
        customer.add_user(user)
        return user

    @pytest.fixture()
    def org_admin_user(self, customer):
        user = create_staff(username="jerry", email="jerry@jerrysplace.com")
        customer.add_user(user)
        return user

    def _get_headers_for_client(
        self,
        user: ToolchainUser,
        repo: Repo,
        audience: AccessTokenAudience = AccessTokenAudience.BUILDSENSE_API,
        impersonation_user: ToolchainUser | None = None,
        restricted: bool = False,
    ) -> dict[str, str]:
        if impersonation_user:
            audience |= AccessTokenAudience.IMPERSONATE
        repo_claims = RepoClaims(
            token_id=None,
            user_api_id=user.api_id,
            customer_pk=repo.customer_id,
            repo_pk=repo.pk,
            username=user.username,
            audience=audience,
            token_type=AccessTokenType.ACCESS_TOKEN,
            impersonated_user_api_id=impersonation_user.api_id if impersonation_user else None,
            restricted=restricted,
        )
        return _get_headers_for_client(user, repo_claims)

    def _get_api_client(
        self,
        user: ToolchainUser,
        repo: Repo,
        *,
        audience: AccessTokenAudience = AccessTokenAudience.BUILDSENSE_API,
        impersonation_user: ToolchainUser | None = None,
        cfg: ClientConfig | None = None,
        restricted: bool = False,
        user_agent="pants/v2.9.0rc0 toolchain/v0.16.0",
    ) -> APIClient:
        headers = self._get_headers_for_client(user, repo, audience, impersonation_user, restricted)
        return CompressibleAPIClient(cfg=cfg or ClientConfig.default(), user_agent=user_agent, **headers)

    @pytest.fixture(params=[True, False])
    def use_compression(self, request) -> bool:
        return request.param

    @pytest.fixture(params=[False])
    def client_config(self, use_compression: bool, request) -> ClientConfig:
        return ClientConfig(use_compression=use_compression, use_file_upload=request.param)

    @pytest.fixture(params=[AccessTokenAudience.for_pants_client(), AccessTokenAudience.BUILDSENSE_API])
    def token_audience(self, request) -> AccessTokenAudience:
        return request.param

    @pytest.fixture()
    def client(
        self,
        token_audience: AccessTokenAudience,
        client_config: ClientConfig,
        user: ToolchainUser,
        repo: Repo,
    ):
        return self._get_api_client(
            user=user,
            repo=repo,
            audience=token_audience,
            cfg=client_config,
        )

    @pytest.fixture()
    def org_admin_client(
        self,
        token_audience: AccessTokenAudience,
        client_config: ClientConfig,
        org_admin_user: ToolchainUser,
        repo: Repo,
    ) -> APIClient:
        return self._get_api_client(
            user=org_admin_user,
            repo=repo,
            audience=token_audience,
            impersonation_user=None,
            cfg=client_config,
        )

    @pytest.fixture()
    def repo(self, customer: Customer) -> Repo:
        return Repo.create("acmebotid", customer=customer, name="acmebot")

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_s3(), mock_dynamodb():
            RunInfoTable.create_table()
            create_s3_bucket(self._BUCKET)
            yield

    def _get_s3_object(self, key: str) -> dict | None:
        s3_obj = boto3.resource("s3").Object("fake-test-buildsense-bucket", key)
        try:
            response = s3_obj.get()
        except botocore.exceptions.ClientError as error:
            if error.response["Error"]["Code"] == "NoSuchKey":
                return None
            raise
        return response

    def _get_s3_content(self, key: str) -> tuple[bytes | None, dict]:
        s3_obj = self._get_s3_object(key)
        if not s3_obj:
            return None, {}
        return s3_obj["Body"].read(), s3_obj["Metadata"]

    def _get_s3_json(self, key: str, decompress: bool = False) -> dict | None:
        content, metadata = self._get_s3_content(key)
        if not content:
            return None
        if decompress:
            assert metadata["compression"] == "zlib"
            content = zlib.decompress(content)
        else:
            assert "compression" not in metadata
        return json.loads(content)

    def _post_data_from_fixture(self, fixture: str, client, repo: Repo) -> HttpResponse:
        data = load_fixture(fixture)
        run_id = data["run_info"]["id"]
        return self._post_data(client, repo, run_id, json_data=data)

    def _get_ingestion_url(self, repo: Repo) -> str:
        return f"/api/v1/repos/{repo.customer.slug}/{repo.slug}/buildsense/"

    def _post_data(
        self, client, repo: Repo, run_id: str, json_data: dict | list | None = None, **extra_kwargs
    ) -> HttpResponse:
        return client.post(
            f"{self._get_ingestion_url(repo)}{run_id}/", data=json_data, format="toolchain_json_data", **extra_kwargs
        )

    def _patch_data(
        self,
        client,
        repo: Repo,
        run_id: str,
        files_dict: dict | None = None,
        json_data: dict | list | None = None,
        **extra_kwargs,
    ) -> HttpResponse:
        url = f"{self._get_ingestion_url(repo)}{run_id}/"
        if files_dict:
            assert json_data is None
            return client.patch(url, files_dict, **extra_kwargs)
        if "data" in extra_kwargs:
            return client.patch(url, **extra_kwargs)
        return client.patch(url, data=json_data, format="toolchain_json_data", **extra_kwargs)


class TestBuildsenseIngestionViewAuth(BaseViewsApiTest):
    def test_invalid_audience(
        self,
        user: ToolchainUser,
        repo: Repo,
        customer: Customer,
    ) -> None:
        claims = RepoClaims(
            user_api_id=user.api_id,
            customer_pk=customer.pk,
            repo_pk=repo.pk,
            username="darren",
            audience=AccessTokenAudience.DEPENDENCY_API,
            token_type=AccessTokenType.REFRESH_TOKEN,
            token_id="soup",
            restricted=False,
        )
        client = _get_client_for_user(user, claims)
        response = self._post_data_from_fixture(fixture="sample_9_start", client=client, repo=repo)
        assert response.status_code == 403
        assert response.json() == {"detail": "You do not have permission to perform this action."}

    def test_inactive_user(
        self,
        user: ToolchainUser,
        customer: Customer,
        repo: Repo,
    ) -> None:  # This should never happen.
        claims = RepoClaims(
            user_api_id="mail-fraud",
            customer_pk=customer.pk,
            repo_pk=repo.pk,
            username="darren",
            audience=AccessTokenAudience.BUILDSENSE_API,
            token_type=AccessTokenType.REFRESH_TOKEN,
            token_id="soup",
            restricted=False,
        )
        client = _get_client_for_user(user, claims)
        user.deactivate()
        response = self._post_data_from_fixture(fixture="sample_9_start", client=client, repo=repo)
        assert response.status_code == 403
        assert response.json() == {"detail": "Authentication credentials were not provided."}

    def test_no_auth(self, repo: Repo) -> None:
        client = _get_client(user_agent="no soup for you", extra_headers={})
        response = self._post_data_from_fixture(fixture="sample_9_start", client=client, repo=repo)
        assert response.status_code == 403
        assert response.json() == {"detail": "Authentication credentials were not provided."}


class BaseTestBuildsenseIngestionViewTest(BaseViewsApiTest):
    def _get_fixture_and_run_id(self, fixture: str) -> tuple[str, dict]:
        data = load_fixture(fixture)
        return data["run_info"]["id"], data

    def _assert_table_data(
        self, repo: Repo, user: ToolchainUser, run_id: str, timestamp: datetime.datetime, key_suffix: str
    ) -> RunInfo:
        table = RunInfoTable.for_customer_id(repo.customer_id)
        run_info = table.get_by_run_id(repo_id=repo.pk, user_api_id=user.api_id, run_id=run_id)
        assert run_info.run_id == run_id
        assert run_info.repo_id == repo.pk
        assert run_info.timestamp == timestamp
        assert run_info.server_info.s3_bucket == "fake-test-buildsense-bucket"
        assert (
            run_info.server_info.s3_key
            == f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.id}/{user.api_id}/{key_suffix}"
        )
        assert run_info.server_info.client_ip == "35.175.222.211"
        return run_info


class TestBuildsenseIngestionView_Basic(BaseTestBuildsenseIngestionViewTest):
    def test_post_bad_data(self, repo: Repo, client) -> None:
        run_id, data = self._get_fixture_and_run_id("sample_9_start")
        response = self._post_data(client, repo, run_id, json_data=[data])
        assert response.status_code == 400
        assert response.json() == {"error": {"message": "Unexpected buildsense data (must be dict)"}}
        assert ProcessPantsRun.objects.count() == 0

    def test_patch_bad_data(self, repo: Repo, client) -> None:
        run_id, data = self._get_fixture_and_run_id("sample_9_end")
        response = self._patch_data(client, repo, run_id, json_data=[data])
        assert response.status_code == 400
        assert response.json() == {"error": {"message": "Unexpected buildsense data (must be dict)"}}
        assert ProcessPantsRun.objects.count() == 0

    def test_post_start_report(self, client, customer: Customer, repo: Repo, user: ToolchainUser) -> None:
        run_id, fixture_data = self._get_fixture_and_run_id("sample_9_start")
        response = self._post_data(client, repo, run_id, json_data=fixture_data)
        assert response.status_code == 201
        assert response.json() == {
            "ci_user_api_id": None,
            "saved": True,
            "link": "http://testserver/organizations/acmeid/repos/acmebotid/builds/pants_run_2020_01_23_11_41_55_931_68189fba67f94d7ebd9b119f4966124c/",
        }
        run_info = self._assert_table_data(
            repo=repo,
            user=user,
            run_id=run_id,
            timestamp=datetime.datetime(2020, 1, 23, 19, 41, 55, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2020_01_23_11_41_55_931_68189fba67f94d7ebd9b119f4966124c/start.json",
        )
        assert self._get_s3_json(run_info.server_info.s3_key) == fixture_data
        assert ProcessPantsRun.objects.count() == 0

    def test_post_start_and_end_reports(self, client, customer: Customer, repo: Repo, user: ToolchainUser) -> None:
        start_run_id, start_data = self._get_fixture_and_run_id("sample_9_start")
        end_run_id, end_data = self._get_fixture_and_run_id("sample_9_end")
        assert start_run_id == end_run_id
        response = self._post_data(client, repo, start_run_id, json_data=start_data)
        assert response.status_code == 201
        assert response.json() == {
            "ci_user_api_id": None,
            "saved": True,
            "link": "http://testserver/organizations/acmeid/repos/acmebotid/builds/pants_run_2020_01_23_11_41_55_931_68189fba67f94d7ebd9b119f4966124c/",
        }
        assert ProcessPantsRun.objects.count() == 0
        response = self._patch_data(client, repo, start_run_id, json_data=end_data)
        assert response.status_code == 201
        run_info = self._assert_table_data(
            repo=repo,
            user=user,
            run_id=start_run_id,
            timestamp=datetime.datetime(2020, 1, 23, 19, 41, 55, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2020_01_23_11_41_55_931_68189fba67f94d7ebd9b119f4966124c/final.json",
        )

        assert self._get_s3_json(run_info.server_info.s3_key) == end_data
        raw_data_start = self._get_s3_json(
            f"no-soup-for-you/buildsense/storage/{customer.id}/{repo.id}/{user.api_id}/{end_run_id}/start.json"
        )
        assert raw_data_start == start_data
        assert ProcessPantsRun.objects.count() == 1
        ppr = ProcessPantsRun.objects.first()
        assert ppr.repo_id == repo.pk
        assert ppr.user_api_id == user.api_id
        assert ppr.run_id == start_run_id

    def test_post_start_report_repo_mismatch(self, client, customer: Customer, repo: Repo, user: ToolchainUser) -> None:
        run_id, fixture_data = self._get_fixture_and_run_id("sample_9_start")
        repo_2 = Repo.create("bob", customer=customer, name="Bob Sacamano")
        response = self._post_data(client, repo_2, run_id, json_data=fixture_data)
        assert response.status_code == 403
        assert response.json() == {"detail": "Invalid repo slug: bob"}

    @pytest.mark.parametrize(
        "user_agent",
        ["pants/v2.9.0rc0+gita0a1a7d5 toolchain/v0.17.0", "Mozilla/5.0 Chrome/96.0.4664.110 Safari/537.36"],
    )
    def test_post_end_report_with_user_agent(self, repo: Repo, user: ToolchainUser, user_agent: str) -> None:
        client = self._get_api_client(user, repo, user_agent=user_agent)
        run_id, data = self._get_fixture_and_run_id("run_with_pex_failure")
        response = self._patch_data(client, repo, run_id, json_data=data)
        assert response.status_code == 201
        self._assert_table_data(
            repo=repo,
            user=user,
            run_id=run_id,
            timestamp=datetime.datetime(2020, 10, 13, 17, 45, 53, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2020_10_13_10_45_53_495_c60f37108a5f4b709312649ced9cca2a/final.json",
        )
        assert ProcessPantsRun.objects.count() == 1

    def test_post_end_report_invalid_content_length(self, client, repo: Repo, user: ToolchainUser) -> None:
        run_id, data = self._get_fixture_and_run_id("run_with_pex_failure")
        response = self._patch_data(client, repo, run_id, json_data=data, HTTP_CONTENT_LENGTH="bob")
        assert response.status_code == 201
        self._assert_table_data(
            repo=repo,
            user=user,
            run_id=run_id,
            timestamp=datetime.datetime(2020, 10, 13, 17, 45, 53, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2020_10_13_10_45_53_495_c60f37108a5f4b709312649ced9cca2a/final.json",
        )
        assert ProcessPantsRun.objects.count() == 1

    FORBIDDEN_FIELDS_COMBOS = (
        ("indicators",),
        ("modified_fields",),
        ("modified_fields", "indicators"),
        ("collected_platform_info",),
        ("modified_fields", "collected_platform_info", "indicators"),
    )

    @pytest.mark.parametrize("fields", FORBIDDEN_FIELDS_COMBOS)
    def test_post_end_report_with_forbidden_fields(
        self, client, repo: Repo, user: ToolchainUser, fields: tuple[str, ...]
    ) -> None:
        run_id, data = self._get_fixture_and_run_id("run_with_pex_failure")
        for field in fields:
            data["run_info"][field] = "no soup for you"
        response = self._patch_data(client, repo, run_id, json_data=data)
        assert response.status_code == 400
        assert response.json() == {"error": {"message": "Forbidden fields in build data"}}
        assert get_table_items_count() == 0
        key = f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.id}/{user.api_id}/pants_run_2020_10_13_10_45_53_495_c60f37108a5f4b709312649ced9cca2a/final.json"
        assert data == json.loads(S3().get_content(bucket=self._BUCKET, key=key))
        assert ProcessPantsRun.objects.count() == 0

    @pytest.mark.parametrize("fields", FORBIDDEN_FIELDS_COMBOS)
    def test_post_start_report_with_forbidden_fields(
        self, client, repo: Repo, user: ToolchainUser, fields: tuple[str, ...]
    ) -> None:
        run_id, data = self._get_fixture_and_run_id("run_with_pex_failure")
        for field in fields:
            data["run_info"][field] = "no soup for you"
        response = self._post_data(client, repo, run_id, json_data=data)
        assert response.status_code == 400
        assert response.json() == {"error": {"message": "Forbidden fields in build data"}}
        assert get_table_items_count() == 0
        key = f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.id}/{user.api_id}/pants_run_2020_10_13_10_45_53_495_c60f37108a5f4b709312649ced9cca2a/start.json"
        assert data == json.loads(S3().get_content(bucket=self._BUCKET, key=key))
        assert ProcessPantsRun.objects.count() == 0


class TestBuildsenseIngestionView_CircleCI(BaseTestBuildsenseIngestionViewTest):
    def test_post_start_report_with_circle_ci_unknown_user(
        self, client, httpx_mock, customer: Customer, repo: Repo, user: ToolchainUser
    ) -> None:
        run_id, fixture_data = self._get_fixture_and_run_id("ci_build_pr_start_2")
        add_resolve_user_response_fail(httpx_mock, user=user, customer_id=customer.id, github_user_id="1268088")
        add_github_pr_response_for_repo(httpx_mock, repo, 6490, "pull_request_assigned")
        response = self._post_data(client, repo, run_id, json_data=fixture_data)
        assert response.status_code == 201
        assert response.json() == {
            "ci_user_api_id": None,
            "saved": True,
            "link": "http://testserver/organizations/acmeid/repos/acmebotid/builds/pants_run_2020_08_13_00_21_45_933_7b6b93239b1e4a329e7de2c7bc65ce1f/",
        }
        run_info = self._assert_table_data(
            repo=repo,
            user=user,
            run_id=run_id,
            timestamp=datetime.datetime(2020, 8, 13, 0, 21, 45, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2020_08_13_00_21_45_933_7b6b93239b1e4a329e7de2c7bc65ce1f/start.json",
        )
        # We supplement missing pants data from CI
        fixture_data["run_info"].update(revision="c5454b4327903b7d2242f705e9218ca90bcc7e49", branch="pull/6490")
        assert self._get_s3_json(run_info.server_info.s3_key) == fixture_data
        assert ProcessPantsRun.objects.count() == 0

    def test_post_start_report_with_circle_ci_impersonation_denied(
        self, client, httpx_mock, customer: Customer, repo: Repo, user: ToolchainUser
    ) -> None:
        add_resolve_user_response_fail(
            httpx_mock, user=user, customer_id=customer.id, github_user_id="1268088", status=403
        )
        add_github_pr_response_for_repo(httpx_mock, repo, 6490, "pull_request_assigned")
        run_id, fixture_data = self._get_fixture_and_run_id("ci_build_pr_start_1")
        response = self._post_data(client, repo, run_id, json_data=fixture_data)
        assert response.status_code == 201
        assert response.json() == {
            "ci_user_api_id": None,
            "saved": True,
            "link": "http://testserver/organizations/acmeid/repos/acmebotid/builds/pants_run_2020_08_13_00_21_00_240_87ceaef8db824ad9ac25fa866e988427/",
        }
        run_info = self._assert_table_data(
            repo=repo,
            user=user,
            run_id=run_id,
            timestamp=datetime.datetime(2020, 8, 13, 0, 21, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2020_08_13_00_21_00_240_87ceaef8db824ad9ac25fa866e988427/start.json",
        )
        # We supplement missing pants data from CI
        fixture_data["run_info"].update(revision="c5454b4327903b7d2242f705e9218ca90bcc7e49", branch="pull/6490")
        assert self._get_s3_json(run_info.server_info.s3_key) == fixture_data
        assert ProcessPantsRun.objects.count() == 0

    def test_post_start_report_with_circle_ci(
        self, httpx_mock, org_admin_client, customer: Customer, repo: Repo, org_admin_user: ToolchainUser
    ) -> None:
        add_github_pr_response_for_repo(httpx_mock, repo, 6490, "pull_request_assigned")
        ci_user = create_github_user_and_response(
            httpx_mock, customer, username="foa", github_username="asherf", github_user_id="1268088"
        )
        customer.add_user(ci_user)
        run_id, fixture_data = self._get_fixture_and_run_id("ci_build_pr_start_2")
        response = self._post_data(org_admin_client, repo, run_id, json_data=fixture_data)
        assert response.status_code == 201
        assert response.json() == {
            "ci_user_api_id": ci_user.api_id,
            "saved": True,
            "link": "http://testserver/organizations/acmeid/repos/acmebotid/builds/pants_run_2020_08_13_00_21_45_933_7b6b93239b1e4a329e7de2c7bc65ce1f/",
        }
        run_info = self._assert_table_data(
            repo=repo,
            user=ci_user,
            run_id=run_id,
            timestamp=datetime.datetime(2020, 8, 13, 0, 21, 45, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2020_08_13_00_21_45_933_7b6b93239b1e4a329e7de2c7bc65ce1f/start.json",
        )
        # We supplement missing pants data from CI
        fixture_data["run_info"].update(revision="c5454b4327903b7d2242f705e9218ca90bcc7e49", branch="pull/6490")
        assert self._get_s3_json(run_info.server_info.s3_key) == fixture_data
        assert ProcessPantsRun.objects.count() == 0

    def test_post_start_report_with_circle_ci_and_pr_info_timeout(
        self, httpx_mock, org_admin_client, customer: Customer, repo: Repo, org_admin_user: ToolchainUser
    ) -> None:
        add_pr_response_exception_for_repo(httpx_mock, repo, 6490, exception_cls=httpx.ReadTimeout)
        run_id, fixture_data = self._get_fixture_and_run_id("ci_build_pr_start_2")
        response = self._post_data(org_admin_client, repo, run_id, json_data=fixture_data)
        assert response.status_code == 201
        assert response.json() == {
            "ci_user_api_id": None,
            "saved": True,
            "link": "http://testserver/organizations/acmeid/repos/acmebotid/builds/pants_run_2020_08_13_00_21_45_933_7b6b93239b1e4a329e7de2c7bc65ce1f/",
        }
        run_info = self._assert_table_data(
            repo=repo,
            user=org_admin_user,
            run_id=run_id,
            timestamp=datetime.datetime(2020, 8, 13, 0, 21, 45, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2020_08_13_00_21_45_933_7b6b93239b1e4a329e7de2c7bc65ce1f/start.json",
        )
        fixture_data["run_info"].update(revision="c5454b4327903b7d2242f705e9218ca90bcc7e49", branch="pull/6490")
        assert self._get_s3_json(run_info.server_info.s3_key) == fixture_data
        assert ProcessPantsRun.objects.count() == 0

    def test_post_end_report_with_circle_ci_and_pr_info_timeout(
        self, httpx_mock, org_admin_client, customer: Customer, repo: Repo, org_admin_user: ToolchainUser
    ) -> None:
        add_pr_response_exception_for_repo(httpx_mock, repo, 6490, exception_cls=httpx.ReadTimeout)
        run_id, fixture_data = self._get_fixture_and_run_id("ci_build_pr_start_2")
        response = self._patch_data(org_admin_client, repo, run_id, json_data=fixture_data)
        assert response.status_code == 201
        assert response.json() == {
            "created": True,
            "link": "http://testserver/organizations/acmeid/repos/acmebotid/builds/pants_run_2020_08_13_00_21_45_933_7b6b93239b1e4a329e7de2c7bc65ce1f/",
        }
        run_info = self._assert_table_data(
            repo=repo,
            user=org_admin_user,
            run_id=run_id,
            timestamp=datetime.datetime(2020, 8, 13, 0, 21, 45, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2020_08_13_00_21_45_933_7b6b93239b1e4a329e7de2c7bc65ce1f/final.json",
        )
        fixture_data["run_info"].update(revision="c5454b4327903b7d2242f705e9218ca90bcc7e49", branch="pull/6490")
        assert self._get_s3_json(run_info.server_info.s3_key) == fixture_data
        assert ProcessPantsRun.objects.count() == 1

    def test_resolve_pull_request_circle_ci_user_from_github(
        self, httpx_mock, org_admin_client, customer: Customer, repo: Repo, org_admin_user: ToolchainUser
    ) -> None:
        add_github_pr_response_for_repo(httpx_mock, repo, 6490, "pull_request_assigned")
        ci_user = create_github_user_and_response(
            httpx_mock, customer, username="foa", github_username="asherf", github_user_id="1268088"
        )
        customer.add_user(ci_user)
        run_id, fixture_data = self._get_fixture_and_run_id("ci_build_pr_final_2")
        fixture_data["ci_env"]["CIRCLE_USERNAME"] = ""
        fixture_data["ci_env"]["CIRCLE_PR_USERNAME"] = ""
        response = self._patch_data(org_admin_client, repo, run_id, json_data=fixture_data)
        assert response.status_code == 201
        assert response.json() == {
            "created": True,
            "link": "http://testserver/organizations/acmeid/repos/acmebotid/builds/pants_run_2020_08_13_00_21_45_933_7b6b93239b1e4a329e7de2c7bc65ce1f/",
        }
        run_info = self._assert_table_data(
            repo=repo,
            user=ci_user,
            run_id=run_id,
            timestamp=datetime.datetime(2020, 8, 13, 0, 21, 45, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2020_08_13_00_21_45_933_7b6b93239b1e4a329e7de2c7bc65ce1f/final.json",
        )
        assert run_info.ci_info is not None
        assert run_info.ci_info.username == "asherf"
        assert self._get_s3_json(run_info.server_info.s3_key) == fixture_data
        assert ProcessPantsRun.objects.count() == 1

    def test_resolve_branch_circle_ci_user_from_github(
        self, httpx_mock, org_admin_client, customer: Customer, repo: Repo, org_admin_user: ToolchainUser
    ) -> None:
        add_github_push_response_for_repo(
            httpx_mock,
            repo,
            branch="master",
            commit_sha="3962394f3b3413389c911d3cfb9dbf45fe735a1f",
            fixture="repo_push",
        )
        ci_user = create_github_user_and_response(
            httpx_mock, customer, username="benjy", github_username="benjyw", github_user_id="512764"
        )
        customer.add_user(ci_user)
        run_id, fixture_data = self._get_fixture_and_run_id("ci_build_branch_final_1")
        fixture_data["ci_env"]["CIRCLE_USERNAME"] = ""
        fixture_data["ci_env"]["CIRCLE_PR_USERNAME"] = ""
        response = self._patch_data(org_admin_client, repo, run_id, json_data=fixture_data)
        assert response.status_code == 201
        assert response.json() == {
            "created": True,
            "link": "http://testserver/organizations/acmeid/repos/acmebotid/builds/pants_run_2020_08_14_17_17_32_751_5263973c8e154a7fb3d8f98232dd24f2/",
        }
        run_info = self._assert_table_data(
            repo=repo,
            user=ci_user,
            run_id=run_id,
            timestamp=datetime.datetime(2020, 8, 14, 17, 17, 32, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2020_08_14_17_17_32_751_5263973c8e154a7fb3d8f98232dd24f2/final.json",
        )
        assert run_info.ci_info is not None
        assert run_info.ci_info.username == "benjyw"
        assert self._get_s3_json(run_info.server_info.s3_key) == fixture_data
        assert ProcessPantsRun.objects.count() == 1

    def test_post_end_report(self, client, httpx_mock, customer: Customer, repo: Repo, user: ToolchainUser) -> None:
        run_id, fixture_data = self._get_fixture_and_run_id("ci_build_pr_final_1")
        add_github_pr_response_for_repo(httpx_mock, repo, 6490, "pull_request_review_requested")
        add_resolve_user_response_fail(httpx_mock, user=user, customer_id=customer.id, github_user_id="1268088")
        response = self._patch_data(client, repo, run_id, json_data=fixture_data)
        assert response.status_code == 201
        run_info = self._assert_table_data(
            repo=repo,
            user=user,
            run_id=run_id,
            timestamp=datetime.datetime(2020, 8, 13, 0, 21, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2020_08_13_00_21_00_240_87ceaef8db824ad9ac25fa866e988427/final.json",
        )
        assert run_info.ci_info is not None
        assert run_info.ci_info.build_num == 22579
        assert run_info.ci_info.pull_request == 6490
        assert run_info.ci_info.run_type == run_info.ci_info.Type.PULL_REQUEST
        assert run_info.ci_info.build_url == "https://circleci.com/gh/toolchainlabs/toolchain/22579"
        assert run_info.ci_info.username == "asherf"
        assert self._get_s3_json(run_info.server_info.s3_key) == fixture_data
        assert ProcessPantsRun.objects.count() == 1

    def test_post_start_and_end_reports_with_circle_ci_impersonation(
        self,
        httpx_mock,
        org_admin_client,
        customer: Customer,
        repo: Repo,
        org_admin_user: ToolchainUser,
        client_config: ClientConfig,
    ) -> None:
        add_github_pr_response_for_repo(httpx_mock, repo, 6490, "pull_request_review_requested")
        ci_user = create_github_user_and_response(
            httpx_mock, customer, username="foa", github_username="asherf", github_user_id="1268088"
        )
        customer.add_user(ci_user)
        start_run_id, start_data = self._get_fixture_and_run_id("ci_build_pr_start_2")
        end_run_id, end_data = self._get_fixture_and_run_id("ci_build_pr_final_2")
        assert start_run_id == end_run_id
        response = self._post_data(org_admin_client, repo, start_run_id, json_data=start_data)
        assert response.status_code == 201
        assert response.json() == {
            "ci_user_api_id": ci_user.api_id,
            "saved": True,
            "link": "http://testserver/organizations/acmeid/repos/acmebotid/builds/pants_run_2020_08_13_00_21_45_933_7b6b93239b1e4a329e7de2c7bc65ce1f/",
        }
        assert ProcessPantsRun.objects.count() == 0
        client = self._get_api_client(
            user=org_admin_user,
            repo=repo,
            audience=AccessTokenAudience.BUILDSENSE_API,
            impersonation_user=ci_user,
            cfg=client_config,
        )
        response = self._patch_data(client, repo, start_run_id, json_data=end_data)
        assert response.status_code == 201
        run_info = self._assert_table_data(
            repo=repo,
            user=ci_user,
            run_id=start_run_id,
            timestamp=datetime.datetime(2020, 8, 13, 0, 21, 45, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2020_08_13_00_21_45_933_7b6b93239b1e4a329e7de2c7bc65ce1f/final.json",
        )

        assert self._get_s3_json(run_info.server_info.s3_key) == end_data
        raw_data_start = self._get_s3_json(
            f"no-soup-for-you/buildsense/storage/{customer.id}/{repo.id}/{ci_user.api_id}/{end_run_id}/start.json"
        )
        # We supplement missing pants data from CI
        start_data["run_info"].update(revision="c5454b4327903b7d2242f705e9218ca90bcc7e49", branch="pull/6490")
        assert raw_data_start == start_data
        assert ProcessPantsRun.objects.count() == 1
        ppr = ProcessPantsRun.objects.first()
        assert ppr.repo_id == repo.pk
        assert ppr.user_api_id == ci_user.api_id
        assert ppr.run_id == start_run_id

    def test_post_start_and_end_reports_with_circle_ci_empty_username(
        self, httpx_mock, org_admin_client, customer: Customer, repo: Repo, org_admin_user: ToolchainUser
    ) -> None:
        ci_user = create_github_user(username="foa", github_username="asherf", github_user_id="cosmo")
        customer.add_user(ci_user)
        add_github_pr_response_for_repo(httpx_mock, repo, 6490)
        start_run_id, start_data = self._get_fixture_and_run_id("ci_build_pr_start_2")
        start_data["ci_env"]["CIRCLE_USERNAME"] = ""
        start_data["ci_env"]["CIRCLE_PR_USERNAME"] = ""
        end_run_id, end_data = self._get_fixture_and_run_id("ci_build_pr_final_2")
        end_data["ci_env"]["CIRCLE_USERNAME"] = ""
        end_data["ci_env"]["CIRCLE_PR_USERNAME"] = ""
        assert start_run_id == end_run_id
        response = self._post_data(org_admin_client, repo, start_run_id, json_data=start_data)
        assert response.status_code == 201
        assert response.json() == {
            "ci_user_api_id": None,
            "saved": True,
            "link": "http://testserver/organizations/acmeid/repos/acmebotid/builds/pants_run_2020_08_13_00_21_45_933_7b6b93239b1e4a329e7de2c7bc65ce1f/",
        }
        assert ProcessPantsRun.objects.count() == 0
        response = self._patch_data(org_admin_client, repo, start_run_id, json_data=end_data)
        assert response.status_code == 201
        run_info = self._assert_table_data(
            repo=repo,
            user=org_admin_user,
            run_id=start_run_id,
            timestamp=datetime.datetime(2020, 8, 13, 0, 21, 45, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2020_08_13_00_21_45_933_7b6b93239b1e4a329e7de2c7bc65ce1f/final.json",
        )

        assert self._get_s3_json(run_info.server_info.s3_key) == end_data
        raw_data_start = self._get_s3_json(
            f"no-soup-for-you/buildsense/storage/{customer.id}/{repo.id}/{org_admin_user.api_id}/{end_run_id}/start.json"
        )
        # We supplement missing pants data from CI
        start_data["run_info"].update(revision="c5454b4327903b7d2242f705e9218ca90bcc7e49", branch="pull/6490")
        assert raw_data_start == start_data
        assert ProcessPantsRun.objects.count() == 1
        ppr = ProcessPantsRun.objects.first()
        assert ppr.repo_id == repo.pk
        assert ppr.user_api_id == org_admin_user.api_id
        assert ppr.run_id == start_run_id

    def test_post_end_report_with_circle_ci_env(
        self, client, httpx_mock, customer: Customer, user: ToolchainUser, repo: Repo
    ) -> None:
        add_github_pr_response_for_repo(httpx_mock, repo, 6474, "pull_request_synchronize")
        run_id, fixture_data = self._get_fixture_and_run_id("ci_build_pr_env_end")
        del fixture_data["ci_info"]
        add_resolve_user_response_fail(httpx_mock, user=user, customer_id=customer.id, github_user_id="1268088")
        response = self._patch_data(client, repo, run_id, json_data=fixture_data)
        assert response.status_code == 201
        run_info = self._assert_table_data(
            repo=repo,
            user=user,
            run_id=run_id,
            timestamp=datetime.datetime(2020, 8, 11, 15, 31, 56, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2020_08_11_15_31_56_742_c201cbb4e83641c79a10231aab47db72/final.json",
        )
        assert run_info.ci_info is not None
        assert run_info.ci_info.build_num == 22480
        assert run_info.ci_info.pull_request == 6474
        assert run_info.ci_info.run_type == run_info.ci_info.Type.PULL_REQUEST
        assert run_info.ci_info.build_url == "https://circleci.com/gh/toolchainlabs/toolchain/22480"
        assert run_info.ci_info.username == "asherf"
        assert self._get_s3_json(run_info.server_info.s3_key) == fixture_data
        assert ProcessPantsRun.objects.count() == 1

    @pytest.mark.parametrize("max_file_memory_size", [None, 30])
    def test_post_end_report_as_file(
        self,
        client,
        httpx_mock,
        max_file_memory_size,
        settings,
        customer: Customer,
        repo: Repo,
        user: ToolchainUser,
    ) -> None:
        add_github_pr_response_for_repo(httpx_mock, repo, 6490, "pull_request_synchronize")
        add_resolve_user_response_fail(httpx_mock, user=user, customer_id=customer.id, github_user_id="1268088")
        if max_file_memory_size:
            settings.FILE_UPLOAD_MAX_MEMORY_SIZE = max_file_memory_size
        run_id, fixture_data = self._get_fixture_and_run_id("ci_build_pr_final_1")
        fp = BytesIO(zlib.compress(json.dumps(fixture_data).encode()))
        response = self._patch_data(
            client,
            repo,
            run_id,
            files_dict={"buildsense": fp},
            HTTP_X_FORWARDED_FOR="35.175.222.211",
            HTTP_CONTENT_ENCODING="compress",
        )
        assert response.status_code == 201
        run_info = self._assert_table_data(
            repo=repo,
            user=user,
            run_id=run_id,
            timestamp=datetime.datetime(2020, 8, 13, 0, 21, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2020_08_13_00_21_00_240_87ceaef8db824ad9ac25fa866e988427/final.json",
        )
        assert run_info.ci_info is not None
        assert run_info.ci_info.build_num == 22579
        assert run_info.ci_info.pull_request == 6490
        assert run_info.ci_info.run_type == run_info.ci_info.Type.PULL_REQUEST
        assert run_info.ci_info.build_url == "https://circleci.com/gh/toolchainlabs/toolchain/22579"
        assert run_info.ci_info.username == "asherf"
        assert self._get_s3_json(run_info.server_info.s3_key, decompress=True) == fixture_data
        assert ProcessPantsRun.objects.count() == 1

    def test_post_end_report_two_files(self, repo: Repo, user: ToolchainUser) -> None:
        client = self._get_api_client(user, repo)
        run_id, fixture_data = self._get_fixture_and_run_id("ci_build_pr_final_1")
        data = json.dumps(fixture_data).encode()
        fp_1 = BytesIO(zlib.compress(data))
        fp_2 = BytesIO(zlib.compress(data, level=9))
        response = self._patch_data(client, repo, run_id, files_dict={"bs1": fp_1, "bs2": fp_2})
        assert response.status_code == 400
        assert response.json() == {"detail": "Only a single file is supported for this endpoint. files=2"}

    def test_post_end_report_corrupted_header(self, repo: Repo, user: ToolchainUser) -> None:
        client = self._get_api_client(user, repo)
        run_id, fixture_data = self._get_fixture_and_run_id("ci_build_pr_final_1")
        response = self._patch_data(
            client,
            repo,
            run_id,
            json_data=fixture_data,
            HTTP_CONTENT_ENCODING="compress",
        )
        assert response.status_code == 400
        assert response.json() == {
            "detail": "Failed to decompress data: error('Error -3 while decompressing data: incorrect header check')"
        }

    def test_post_end_report_corrupted(self, repo: Repo, user: ToolchainUser) -> None:
        client = self._get_api_client(user, repo)
        run_id, fixture_data = self._get_fixture_and_run_id("ci_build_pr_final_1")
        data = zlib.compress(json.dumps(fixture_data).encode())
        response = self._patch_data(
            client,
            repo,
            run_id,
            data=data[:-30],
            content_type="application/json",
            HTTP_CONTENT_ENCODING="compress",
        )
        assert response.status_code == 400
        assert response.json() == {
            "detail": "Failed to decompress data: error('Error -5 while decompressing data: incomplete or truncated stream')"
        }

    def test_post_end_report_corrupted_file(self, client, repo: Repo, user: ToolchainUser) -> None:
        client = self._get_api_client(user, repo)
        run_id, fixture_data = self._get_fixture_and_run_id("ci_build_pr_final_1")
        fp = BytesIO(json.dumps(fixture_data).encode())
        response = self._patch_data(
            client, repo, run_id, files_dict={"buildsense": fp}, HTTP_CONTENT_ENCODING="compress"
        )
        assert response.status_code == 400
        assert response.json() == {
            "detail": "Failed to decompress data: error('Error -3 while decompressing data: incorrect header check')"
        }


class TestBuildsenseIngestionView_Travis(BaseTestBuildsenseIngestionViewTest):
    def test_post_end_report_with_travis_ci_env(
        self, httpx_mock, org_admin_client, customer: Customer, repo: Repo
    ) -> None:
        ci_user = create_github_user_and_response(
            httpx_mock, customer, username="tinsel", github_username="asherf", github_user_id="1268088"
        )
        customer.add_user(ci_user)
        run_id, fixture_data = self._get_fixture_and_run_id("travis_ci_build_pr_final_1")
        add_github_pr_response_for_repo(httpx_mock, repo, 14, fixture="pull_request_synchronize")
        response = self._patch_data(org_admin_client, repo, run_id, json_data=fixture_data)
        assert response.status_code == 201
        run_info = self._assert_table_data(
            repo=repo,
            user=ci_user,
            run_id=run_id,
            timestamp=datetime.datetime(2020, 9, 14, 22, 49, 9, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2020_09_14_22_49_09_208_686cbb2fd6c14a8c9e7b843e7a1f6c90/final.json",
        )
        assert run_info.ci_info is not None
        assert run_info.ci_info.build_num == 86
        assert run_info.ci_info.pull_request == 14
        assert run_info.ci_info.run_type == run_info.ci_info.Type.PULL_REQUEST
        assert run_info.ci_info.build_url == "https://travis-ci.com/toolchainlabs/example-python/builds/184295888"
        assert run_info.ci_info.username == "asherf"
        build_data = self._get_s3_json(run_info.server_info.s3_key)
        assert build_data["run_info"].pop("branch") == "festivus"  # type: ignore[index]
        # Sanity check
        assert fixture_data["run_info"].pop("branch") == "4886bc63fe1c270be4e93308fcda04755142256a"
        assert build_data == fixture_data
        assert ProcessPantsRun.objects.count() == 1

    def test_post_build_start_no_scm_data(
        self, httpx_mock, org_admin_client, org_admin_user: ToolchainUser, customer: Customer, repo: Repo
    ) -> None:
        ci_user = create_github_user(username="tinsel", github_username="asherf", github_user_id="cosmo")
        customer.add_user(ci_user)
        run_id, fixture_data = self._get_fixture_and_run_id("travis_branch_start_1")
        response = self._post_data(org_admin_client, repo, run_id, json_data=fixture_data)
        assert response.status_code == 201
        run_info = self._assert_table_data(
            repo=repo,
            user=org_admin_user,
            run_id=run_id,
            timestamp=datetime.datetime(2020, 9, 14, 23, 58, 13, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2020_09_14_23_58_13_748_9e11cd329da54ca9b6aea7ceb0e3addb/start.json",
        )
        assert run_info.branch == "festivus"
        assert run_info.revision is None
        assert run_info.outcome == "NOT_AVAILABLE"

    def test_build_branch(
        self, httpx_mock, org_admin_client, org_admin_user: ToolchainUser, customer: Customer, repo: Repo
    ) -> None:
        ci_user = create_github_user_and_response(
            httpx_mock, customer=customer, username="tinsel", github_username="stuhood", github_user_id="46740"
        )
        customer.add_user(ci_user)
        run_id, fixture_data = self._get_fixture_and_run_id("travis_branch_build")
        add_github_push_response_for_repo(
            httpx_mock,
            repo,
            branch="master",
            commit_sha="e58d40129dfdb2de8cf0c25b9de09479010aa597",
            fixture="pants_master_commit_e58d40",
        )
        response = self._patch_data(org_admin_client, repo, run_id, json_data=fixture_data)
        assert response.status_code == 201
        run_info = self._assert_table_data(
            repo=repo,
            user=ci_user,
            run_id=run_id,
            timestamp=datetime.datetime(2020, 12, 11, 17, 52, 20, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2020_12_11_17_52_20_979_bf2a9125ddd942fea5da2c4d4377e9c4/final.json",
        )
        assert run_info.branch == "master"
        assert run_info.revision == "e58d40129dfdb2de8cf0c25b9de09479010aa597"
        assert run_info.outcome == "SUCCESS"

    def test_build_branch_with_known_ci_user(
        self,
        org_admin_user: ToolchainUser,
        customer: Customer,
        repo: Repo,
        client_config: ClientConfig,
    ) -> None:
        ci_user = create_github_user(username="tinsel", github_username="asherf", github_user_id="cosmo")
        customer.add_user(ci_user)
        client = self._get_api_client(
            user=org_admin_user,
            repo=repo,
            audience=AccessTokenAudience.BUILDSENSE_API,
            impersonation_user=ci_user,
            cfg=client_config,
        )

        run_id, fixture_data = self._get_fixture_and_run_id("travis_branch_build")
        response = self._patch_data(client, repo, run_id, json_data=fixture_data)
        assert response.status_code == 201
        run_info = self._assert_table_data(
            repo=repo,
            user=ci_user,
            run_id=run_id,
            timestamp=datetime.datetime(2020, 12, 11, 17, 52, 20, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2020_12_11_17_52_20_979_bf2a9125ddd942fea5da2c4d4377e9c4/final.json",
        )
        assert run_info.branch == "master"
        assert run_info.revision == "e58d40129dfdb2de8cf0c25b9de09479010aa597"
        assert run_info.outcome == "SUCCESS"


class TestBuildsenseIngestionView_GithubActions(BaseTestBuildsenseIngestionViewTest):
    def test_post_end_report_with_github_actions_ci_env(
        self, httpx_mock, org_admin_client, customer: Customer, repo: Repo
    ) -> None:
        ci_user = create_github_user_and_response(
            httpx_mock, customer, username="tinsel", github_username="asherf", github_user_id="1268088"
        )
        customer.add_user(ci_user)
        run_id, fixture_data = self._get_fixture_and_run_id("run_lint_github_actions_pull_request")
        add_github_pr_response_for_repo(httpx_mock, repo, 8450, fixture="pull_request_synchronize")
        response = self._patch_data(org_admin_client, repo, run_id, json_data=fixture_data)
        assert response.status_code == 201
        run_info = self._assert_table_data(
            repo=repo,
            user=ci_user,
            run_id=run_id,
            timestamp=datetime.datetime(2021, 2, 16, 20, 53, 14, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2021_02_16_20_53_14_711_df87e43300114adea357e741b3b1fe7d/final.json",
        )
        assert run_info.ci_info is not None
        assert run_info.ci_info.build_num == 33
        assert run_info.ci_info.pull_request == 8450
        assert run_info.ci_info.run_type == run_info.ci_info.Type.PULL_REQUEST
        assert run_info.ci_info.build_url == "https://github.com/toolchainlabs/toolchain/actions/runs/572818683"
        assert run_info.ci_info.username == "asherf"
        build_data = self._get_s3_json(run_info.server_info.s3_key)
        assert build_data["run_info"].pop("branch") == "kenny"  # type: ignore[index]
        # Sanity check
        assert fixture_data["run_info"].pop("branch") == "476d0c837e8a9f0c3f4341337447cb4bac141af1"
        assert build_data == fixture_data
        assert ProcessPantsRun.objects.count() == 1

    def test_build_branch(
        self, org_admin_client, httpx_mock, org_admin_user: ToolchainUser, customer: Customer, repo: Repo
    ) -> None:
        ci_user = create_github_user_and_response(
            httpx_mock, customer, username="tinsel", github_username="stuhood", github_user_id="46740"
        )
        customer.add_user(ci_user)
        run_id, fixture_data = self._get_fixture_and_run_id("run_lint_github_actions_branch")
        add_github_push_response_for_repo(
            httpx_mock,
            repo,
            branch="master",
            commit_sha="2881a1115b48ec5d979a67a4d1476d154160eca3",
            fixture="pants_master_commit_e58d40",
        )
        response = self._patch_data(org_admin_client, repo, run_id, json_data=fixture_data)
        assert response.status_code == 201
        run_info = self._assert_table_data(
            repo=repo,
            user=ci_user,
            run_id=run_id,
            timestamp=datetime.datetime(2021, 2, 16, 22, 27, 13, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2021_02_16_22_27_13_625_e962cc44ebf14c469bc646eb5143d0b9/final.json",
        )
        assert run_info.branch == "master"
        assert run_info.revision == "2881a1115b48ec5d979a67a4d1476d154160eca3"
        assert run_info.outcome == "SUCCESS"


class TestBuildsenseIngestionView_BitbucketPipelines(BaseTestBuildsenseIngestionViewTest):
    def test_post_end_report_pull_request(
        self, responses, httpx_mock, org_admin_client, customer: Customer, repo: Repo
    ) -> None:
        ci_user = create_bitbucket_user_and_response(
            httpx_mock,
            customer,
            username="tinsel",
            bitbucket_username="asherf",
            bitbucket_user_id="6059303e630024006fab8c2b",
        )
        customer.add_user(ci_user)
        run_id, fixture_data = self._get_fixture_and_run_id("bitbucket_pr_lint_run")
        add_bitbucket_pr_response_for_repo(httpx_mock, repo, 11, "pullrequest_created")
        response = self._patch_data(org_admin_client, repo, run_id, json_data=fixture_data)
        assert response.status_code == 201
        run_info = self._assert_table_data(
            repo=repo,
            user=ci_user,
            run_id=run_id,
            timestamp=datetime.datetime(2021, 8, 11, 0, 11, 29, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2021_08_11_00_11_30_828_66be5f4f9775442d8b4bd3b9dbb50e55/final.json",
        )
        assert run_info.ci_info is not None
        assert run_info.ci_info.build_num == 29
        assert run_info.ci_info.pull_request == 11
        assert run_info.ci_info.run_type == run_info.ci_info.Type.PULL_REQUEST
        assert (
            run_info.ci_info.build_url
            == "https://bitbucket.org/festivus-miracle/minimal-pants/addon/pipelines/home#!/results/29/steps/%7Baa13f106-c64d-41c6-b68c-5fe26f04bd00%7D"
        )
        assert run_info.ci_info.username == "asherf"
        build_data = self._get_s3_json(run_info.server_info.s3_key)
        assert build_data["run_info"]["branch"] == "upgrades"  # type: ignore[index]
        # Sanity check
        assert build_data == fixture_data
        assert ProcessPantsRun.objects.count() == 1

    def test_post_end_report_pull_request_no_bitbucket_data(
        self, responses, httpx_mock, org_admin_client, org_admin_user: ToolchainUser, customer: Customer, repo: Repo
    ) -> None:
        run_id, fixture_data = self._get_fixture_and_run_id("bitbucket_pr_lint_run")
        add_bitbucket_pr_response_for_repo(httpx_mock, repo, 11)
        response = self._patch_data(org_admin_client, repo, run_id, json_data=fixture_data)
        assert response.status_code == 201
        run_info = self._assert_table_data(
            repo=repo,
            user=org_admin_user,
            run_id=run_id,
            timestamp=datetime.datetime(2021, 8, 11, 0, 11, 29, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2021_08_11_00_11_30_828_66be5f4f9775442d8b4bd3b9dbb50e55/final.json",
        )
        assert run_info.ci_info is not None
        assert run_info.ci_info.build_num == 29
        assert run_info.ci_info.pull_request == 11
        assert run_info.ci_info.run_type == run_info.ci_info.Type.PULL_REQUEST
        assert (
            run_info.ci_info.build_url
            == "https://bitbucket.org/festivus-miracle/minimal-pants/addon/pipelines/home#!/results/29/steps/%7Baa13f106-c64d-41c6-b68c-5fe26f04bd00%7D"
        )
        assert run_info.ci_info.username is None
        build_data = self._get_s3_json(run_info.server_info.s3_key)
        assert build_data["run_info"]["branch"] == "upgrades"  # type: ignore[index]
        # Sanity check
        assert build_data == fixture_data
        assert ProcessPantsRun.objects.count() == 1

    def test_post_end_report_branch(self, httpx_mock, org_admin_client, customer: Customer, repo: Repo) -> None:
        ci_user = create_bitbucket_user_and_response(
            httpx_mock,
            customer,
            username="tinsel",
            bitbucket_username="asherf",
            bitbucket_user_id="6059303e630024006fab8c2b",
        )
        customer.add_user(ci_user)
        run_id, fixture_data = self._get_fixture_and_run_id("bitbucket_branch_lint_run")
        add_bitbucket_push_response_for_repo(
            httpx_mock,
            repo,
            ref_type="branch",
            ref_name="main",
            commit_sha="2a28689353cf6f6dc72f03942c906ca6347d6dfe",
            fixture="repo_push_pr_merge",
        )
        response = self._patch_data(org_admin_client, repo, run_id, json_data=fixture_data)
        assert response.status_code == 201
        run_info = self._assert_table_data(
            repo=repo,
            user=ci_user,
            run_id=run_id,
            timestamp=datetime.datetime(2021, 8, 11, 0, 14, 48, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2021_08_11_00_14_51_48_c840708568b44cf48d76d42491978efb/final.json",
        )
        assert run_info.ci_info is not None
        assert run_info.ci_info.build_num == 30
        assert run_info.ci_info.pull_request is None
        assert run_info.ci_info.run_type == run_info.ci_info.Type.BRANCH
        assert (
            run_info.ci_info.build_url
            == "https://bitbucket.org/festivus-miracle/minimal-pants/addon/pipelines/home#!/results/30/steps/%7B1c6865a9-a4a3-49e1-8187-1f6e67013e38%7D"
        )
        assert run_info.ci_info.username == "asherf"
        build_data = self._get_s3_json(run_info.server_info.s3_key)
        assert build_data["run_info"]["branch"] == "main"  # type: ignore[index]
        # Sanity check
        assert build_data == fixture_data
        assert ProcessPantsRun.objects.count() == 1

    def test_post_end_report_branch_no_bitbucket_data(
        self, httpx_mock, org_admin_client, org_admin_user: ToolchainUser, customer: Customer, repo: Repo
    ) -> None:
        run_id, fixture_data = self._get_fixture_and_run_id("bitbucket_branch_lint_run")
        add_bitbucket_push_response_for_repo(
            httpx_mock,
            repo,
            ref_type="branch",
            ref_name="main",
            commit_sha="2a28689353cf6f6dc72f03942c906ca6347d6dfe",
        )
        response = self._patch_data(org_admin_client, repo, run_id, json_data=fixture_data)
        assert response.status_code == 201
        run_info = self._assert_table_data(
            repo=repo,
            user=org_admin_user,
            run_id=run_id,
            timestamp=datetime.datetime(2021, 8, 11, 0, 14, 48, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2021_08_11_00_14_51_48_c840708568b44cf48d76d42491978efb/final.json",
        )
        assert run_info.ci_info is not None
        assert run_info.ci_info.build_num == 30
        assert run_info.ci_info.pull_request is None
        assert run_info.ci_info.run_type == run_info.ci_info.Type.BRANCH
        assert (
            run_info.ci_info.build_url
            == "https://bitbucket.org/festivus-miracle/minimal-pants/addon/pipelines/home#!/results/30/steps/%7B1c6865a9-a4a3-49e1-8187-1f6e67013e38%7D"
        )
        assert run_info.ci_info.username is None
        build_data = self._get_s3_json(run_info.server_info.s3_key)
        assert build_data["run_info"]["branch"] == "main"  # type: ignore[index]
        # Sanity check
        assert build_data == fixture_data
        assert ProcessPantsRun.objects.count() == 1

    def test_post_end_report_tag(self, httpx_mock, org_admin_client, customer: Customer, repo: Repo) -> None:
        ci_user = create_bitbucket_user_and_response(
            httpx_mock,
            customer,
            username="tinsel",
            bitbucket_username="asherf",
            bitbucket_user_id="6059303e630024006fab8c2b",
        )
        customer.add_user(ci_user)
        run_id, fixture_data = self._get_fixture_and_run_id("bitbucket_tag_lint_run")
        add_bitbucket_push_response_for_repo(
            httpx_mock,
            repo,
            ref_type="tag",
            ref_name="h&h-bagles",
            commit_sha="113feb0671944c44d274fc4d7c32c681427f9011",
            fixture="repo_push_create_tag",
        )
        response = self._patch_data(org_admin_client, repo, run_id, json_data=fixture_data)
        assert response.status_code == 201
        run_info = self._assert_table_data(
            repo=repo,
            user=ci_user,
            run_id=run_id,
            timestamp=datetime.datetime(2021, 8, 12, 0, 53, 48, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2021_08_12_00_53_51_617_f8c6c6871059495ebaef93fb4f3b394f/final.json",
        )
        assert run_info.ci_info is not None
        assert run_info.ci_info.build_num == 33
        assert run_info.ci_info.pull_request is None
        assert run_info.ci_info.run_type == run_info.ci_info.Type.TAG
        assert (
            run_info.ci_info.build_url
            == "https://bitbucket.org/festivus-miracle/minimal-pants/addon/pipelines/home#!/results/33/steps/%7Bf987bb55-e706-49f5-9a2d-6ade1f16ee5f%7D"
        )
        assert run_info.ci_info.username == "asherf"
        build_data = self._get_s3_json(run_info.server_info.s3_key)
        assert build_data["run_info"]["branch"] == "113feb0671944c44d274fc4d7c32c681427f9011"  # type: ignore[index]
        # Sanity check
        assert build_data == fixture_data
        assert ProcessPantsRun.objects.count() == 1


class TestBuildsenseIngestionView_Buildkite(BaseTestBuildsenseIngestionViewTest):
    def test_post_end_report_github_pull_request(
        self, httpx_mock, org_admin_client, customer: Customer, repo: Repo
    ) -> None:
        ci_user = create_github_user_and_response(
            httpx_mock, customer, username="costanza", github_username="asherf", github_user_id="1268088"
        )

        customer.add_user(ci_user)
        run_id, fixture_data = self._get_fixture_and_run_id("buildkite_github_pull_request_lint_run")
        add_github_pr_response_for_repo(httpx_mock, repo, 3, "pull_request_synchronize")
        response = self._patch_data(org_admin_client, repo, run_id, json_data=fixture_data)
        assert response.status_code == 201
        run_info = self._assert_table_data(
            repo=repo,
            user=ci_user,
            run_id=run_id,
            timestamp=datetime.datetime(2021, 9, 21, 23, 6, 10, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2021_09_21_23_06_22_418_68990434198f4bd5b5f8e0aad82d532d/final.json",
        )
        assert run_info.ci_info is not None
        assert run_info.ci_info.build_num == 9
        assert run_info.ci_info.pull_request == 3
        assert run_info.ci_info.run_type == run_info.ci_info.Type.PULL_REQUEST
        assert (
            run_info.ci_info.build_url
            == "https://buildkite.com/toolchain-labs/minimal-pants-github/builds/9#d4bbd917-7dca-4f22-a84f-41a049ae4921"
        )
        assert run_info.ci_info.username == "asherf"
        build_data = self._get_s3_json(run_info.server_info.s3_key)
        assert build_data["run_info"]["branch"] == "jerry"  # type: ignore[index]
        build_data["run_info"]["branch"] = "b3635292e22d7bf19998e9cacf3d31ed4d86c77d"  # type: ignore[index]
        # Sanity check
        assert build_data == fixture_data
        assert ProcessPantsRun.objects.count() == 1

    def test_post_end_report_github_branch(self, httpx_mock, org_admin_client, customer: Customer, repo: Repo) -> None:
        ci_user = create_github_user_and_response(
            httpx_mock, customer, username="costanza", github_username="george", github_user_id="512764"
        )
        customer.add_user(ci_user)
        run_id, fixture_data = self._get_fixture_and_run_id("buildkite_github_branch_lint_run")
        add_github_push_response_for_repo(
            httpx_mock, repo, branch="main", commit_sha="8c72128f7f930dd6658c4b2723f48dc431860e6c", fixture="repo_push"
        )
        response = self._patch_data(org_admin_client, repo, run_id, json_data=fixture_data)
        assert response.status_code == 201
        run_info = self._assert_table_data(
            repo=repo,
            user=ci_user,
            run_id=run_id,
            timestamp=datetime.datetime(2021, 9, 3, 21, 27, 14, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2021_09_03_21_27_24_650_906810e2ea584decb1fa36514f41f2eb/final.json",
        )
        assert run_info.ci_info is not None
        assert run_info.ci_info.build_num == 3
        assert run_info.ci_info.pull_request is None
        assert run_info.ci_info.run_type == run_info.ci_info.Type.BRANCH
        assert (
            run_info.ci_info.build_url
            == "https://buildkite.com/toolchain-labs/minimal-pants-github/builds/3#e5e98dcf-23f0-48d4-87f0-c1ffbf023c2a"
        )
        assert run_info.ci_info.username == "george"
        build_data = self._get_s3_json(run_info.server_info.s3_key)
        assert build_data["run_info"]["branch"] == "main"  # type: ignore[index]
        build_data["run_info"]["branch"] = "8c72128f7f930dd6658c4b2723f48dc431860e6c"  # type: ignore[index]
        # Sanity check
        assert build_data == fixture_data
        assert ProcessPantsRun.objects.count() == 1


class TestBuildsenseIngestionView_SantizeData(BaseTestBuildsenseIngestionViewTest):
    def test_post_long_cmd_line(self, client, user: ToolchainUser, customer: Customer, repo: Repo) -> None:
        run_id, fixture_data = self._get_fixture_and_run_id("pants_piping_run")
        run_info = fixture_data["run_info"]
        # Adding more data like in the real build (toolchain repo pants_run_2021_10_04_11_45_25_63_d1918943820c43a78258141ca9fd2739)
        # But doing it from code to avoid storing a large fixture in github.
        extra_data = [f"src/bob/jerry/seinfeld/file_{x}.py" for x in range(10_000)]
        run_info["cmd_line"] = run_info["cmd_line"] + " ".join(extra_data)
        run_info["specs_from_command_line"].append(extra_data)
        response = self._patch_data(client, repo, run_id, json_data=fixture_data)
        assert response.status_code == 201
        run_info = self._assert_table_data(
            repo=repo,
            user=user,
            run_id=run_id,
            timestamp=datetime.datetime(2021, 10, 4, 18, 45, 24, tzinfo=datetime.timezone.utc),
            key_suffix="pants_run_2021_10_04_11_45_25_63_d1918943820c43a78258141ca9fd2739/final.json",
        )
        assert run_info.ci_info is None
        build_data = self._get_s3_json(run_info.server_info.s3_key)
        assert build_data["run_info"]["branch"] == "george"  # type: ignore[index]
        # Sanity check
        assert build_data == fixture_data
        assert ProcessPantsRun.objects.count() == 1


class TestWorkunitsIngestionView(BaseViewsApiTest):
    def _post_work_units(self, client, repo: Repo, run_id: str, json_data: dict) -> HttpResponse:
        url = f"/api/v1/repos/{repo.customer.slug}/{repo.slug}/buildsense/{run_id}/workunits/"
        return client.post(url, data=json.dumps(json_data), content_type="application/json")

    def test_ingest_workunits(self, client, user: ToolchainUser, repo: Repo) -> None:
        response = self._post_data_from_fixture(fixture="sample_9_start", client=client, repo=repo)
        assert response.status_code == 201
        run_id = "pants_run_2020_01_23_11_41_55_931_68189fba67f94d7ebd9b119f4966124c"
        work_unit = {
            "name": "chicken",
            "workunit_id": "little-jerry-seinfeld",
            "start": 1569262804.8273,
            "last_update": 1569262818.825,
            "version": 2,
            "state": "running",
        }
        response = self._post_work_units(client, repo, run_id, json_data={"workunits": [work_unit]})
        assert response.status_code == 201

    def test_ingest_workunits_no_table_entry(self, client, user: ToolchainUser, repo: Repo) -> None:
        run_id = "pants_run_2020_01_23_11_41_55_931_68189fba67f94d7ebd9b119f4966124c"

        work_unit = {
            "name": "chicken",
            "workunit_id": "little-jerry-seinfeld",
            "start": 1569262804.8273,
            "last_update": 1569262818.825,
            "version": 2,
            "state": "running",
        }
        response = self._post_work_units(client, repo, run_id, json_data={"workunits": [work_unit]})
        assert response.status_code == 200  # Should probably be an http error


class TestBuildsenseBatchIngestionView(BaseViewsApiTest):
    def _get_fixtures(self, fixtures: Sequence[str]) -> dict[str, dict]:
        builds = {}
        for name in fixtures:
            data = load_fixture(name)
            run_id = data["run_info"]["id"]
            builds[run_id] = data
        return builds

    def _post_batch(self, client, repo: Repo, json_data) -> HttpResponse:
        return client.post(
            f"{self._get_ingestion_url(repo)}batch/",
            data=json.dumps(json_data),
            content_type="application/json",
        )

    def test_post_empty_batch(self, client, user: ToolchainUser, repo: Repo) -> None:
        response = self._post_batch(client, repo, json_data={"builds": [], "version": "1"})
        assert response.status_code == 400
        assert response.json() == {"error": {"message": "Invalid payload"}}
        assert ProcessQueuedBuilds.objects.count() == 0

    def test_post_batch_missing_version(self, client, user: ToolchainUser, repo: Repo) -> None:
        builds = self._get_fixtures(["sample_10_finish", "ci_build_pr_final_2"])
        response = self._post_batch(client, repo, json_data={"build_stats": builds})
        assert response.status_code == 400
        assert response.json() == {"error": {"message": "Missing version data"}}
        assert ProcessQueuedBuilds.objects.count() == 0

    def test_post_batch_v1(self, client, user: ToolchainUser, repo: Repo) -> None:
        assert ProcessQueuedBuilds.objects.count() == 0
        builds = self._get_fixtures(["sample_10_finish", "ci_build_pr_final_2"])
        response = self._post_batch(client, repo, json_data={"build_stats": builds, "version": "1"})
        assert response.status_code == 201
        assert ProcessQueuedBuilds.objects.count() == 1

    def test_post_batch_unsupported_version(self, client, user: ToolchainUser, repo: Repo) -> None:
        builds = self._get_fixtures(["sample_10_finish", "ci_build_pr_final_2"])
        response = self._post_batch(client, repo, json_data={"build_stats": builds, "version": "22"})
        assert response.status_code == 400
        assert response.json() == {"error": {"message": "Invalid version data"}}
        assert ProcessQueuedBuilds.objects.count() == 0


class TestBuildsenseArtifactsIngestionView(BaseViewsApiTest):
    def _create_sqllite_db(self, tmp_path: Path) -> bytes:
        db_file = tmp_path / "data.db"
        conn = sqlite3.connect(db_file.as_posix())
        conn.cursor().execute("CREATE TABLE meta ([key] TEXT,value TEXT, UNIQUE ([key]));")
        conn.close()
        return db_file.read_bytes()

    @pytest.fixture(params=[None, 10])
    def client(  # type: ignore[override]
        self,
        settings,
        token_audience: AccessTokenAudience,
        user: ToolchainUser,
        repo: Repo,
        request,
    ) -> APIClient:
        max_size = request.param
        if max_size:
            settings.FILE_UPLOAD_MAX_MEMORY_SIZE = max_size
        return self._get_api_client(
            user=user,
            repo=repo,
            audience=token_audience,
            impersonation_user=None,
            # We do actually compress and use files but this is handled by the tests themselves.
            # The view (ArtifactsIngestionView) is also hard coded to expect multipart upload and compressed files.
            cfg=ClientConfig.default(),
        )

    def _prep_file(self, data) -> BytesIO:
        if isinstance(data, (list, dict)):
            data = json.dumps(data)
        if isinstance(data, str):
            data = data.encode()
        return BytesIO(zlib.compress(data))

    def _post_artifacts(self, client, repo: Repo, run_id: str, files: dict[str, BytesIO]) -> HttpResponse:
        return client.post(f"{self._get_ingestion_url(repo)}{run_id}/artifacts/", files)

    def test_upload_artifact(self, client, tmp_path: Path, user: ToolchainUser, repo: Repo) -> None:
        self._post_data_from_fixture(fixture="sample_9_start", client=client, repo=repo)
        run_id = "pants_run_2020_01_23_11_41_55_931_68189fba67f94d7ebd9b119f4966124c"
        descriptors = {
            "machu": {"workunit_id": "6d37ce18ca3394f7", "name": "coverage_raw", "path": ".coverage"},
            "picchu": {
                "workunit_id": "952ecacad7b29516",
                "name": "xml_results",
                "path": "dist/src.python.toolchain.aws.secretsmanager_test.py.tests.xml",
            },
        }
        xml_data = load_bytes_fixture("test_classes_fail.xml")
        db_data = self._create_sqllite_db(tmp_path)
        files = {
            "descriptors.json": self._prep_file(descriptors),
            "machu": self._prep_file(db_data),
            "picchu": self._prep_file(xml_data),
        }
        response = self._post_artifacts(client, repo, run_id, files)
        assert response.status_code == 201
        base_key = f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.id}/{user.api_id}/{run_id}"
        xml_results_obj = self._get_s3_object(
            f"{base_key}/xml_results_dist_src.python.toolchain.aws.secretsmanager_test.py.tests.xml"
        )
        assert xml_results_obj is not None
        assert zlib.decompress(xml_results_obj["Body"].read()) == xml_data  # type: ignore[index]
        assert xml_results_obj["ContentType"] == "application/xml"  # type: ignore[index]
        assert xml_results_obj["Metadata"] == {  # type: ignore[index]
            "workunit_id": "952ecacad7b29516",
            "name": "xml_results",
            "path": "dist/src.python.toolchain.aws.secretsmanager_test.py.tests.xml",
            "compression": "zlib",
        }

        db_data_obj = self._get_s3_object(f"{base_key}/coverage_raw_.coverage")
        assert zlib.decompress(db_data_obj["Body"].read()) == db_data  # type: ignore[index]
        assert db_data_obj["ContentType"] == "application/octet-stream"  # type: ignore[index]
        assert db_data_obj["Metadata"] == {  # type: ignore[index]
            "workunit_id": "6d37ce18ca3394f7",
            "name": "coverage_raw",
            "path": ".coverage",
            "compression": "zlib",
        }

    def test_upload_artifact_with_pants_log(self, client, user: ToolchainUser, repo: Repo) -> None:
        self._post_data_from_fixture(fixture="sample_9_start", client=client, repo=repo)
        run_id = "pants_run_2020_01_23_11_41_55_931_68189fba67f94d7ebd9b119f4966124c"
        descriptors = {
            "picchu": {
                "workunit_id": "952ecacad7b29516",
                "name": "xml_results",
                "path": "dist/src.python.toolchain.aws.secretsmanager_test.py.tests.xml",
            },
        }
        xml_data = load_bytes_fixture("test_classes_fail.xml")
        files = {
            "descriptors.json": self._prep_file(descriptors),
            "pants_run_log": self._prep_file(
                "How can I go on a cruise with out my cabana wear?\nI love those, those clothes."
            ),
            "picchu": self._prep_file(xml_data),
        }
        response = self._post_artifacts(client, repo, run_id, files)
        assert response.status_code == 201
        base_key = f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.id}/{user.api_id}/{run_id}"
        xml_results_obj = self._get_s3_object(
            f"{base_key}/xml_results_dist_src.python.toolchain.aws.secretsmanager_test.py.tests.xml"
        )
        assert xml_results_obj is not None
        assert zlib.decompress(xml_results_obj["Body"].read()) == xml_data  # type: ignore[index]
        assert xml_results_obj["ContentType"] == "application/xml"  # type: ignore[index]
        assert xml_results_obj["Metadata"] == {  # type: ignore[index]
            "workunit_id": "952ecacad7b29516",
            "name": "xml_results",
            "path": "dist/src.python.toolchain.aws.secretsmanager_test.py.tests.xml",
            "compression": "zlib",
        }

        pants_log_obj = self._get_s3_object(f"{base_key}/pants_run_log.txt")
        assert zlib.decompress(pants_log_obj["Body"].read()) == b"How can I go on a cruise with out my cabana wear?\nI love those, those clothes."  # type: ignore[index]
        assert pants_log_obj["ContentType"] == "text/plain"  # type: ignore[index]
        assert pants_log_obj["Metadata"] == {"compression": "zlib"}  # type: ignore[index]

    def test_upload_pants_log(self, client, user: ToolchainUser, repo: Repo) -> None:
        self._post_data_from_fixture(fixture="sample_9_start", client=client, repo=repo)
        run_id = "pants_run_2020_01_23_11_41_55_931_68189fba67f94d7ebd9b119f4966124c"
        files = {
            "pants_run_log": self._prep_file(
                "How can I go on a cruise with out my cabana wear?\nI love those, those clothes."
            ),
        }
        response = self._post_artifacts(client, repo, run_id, files)
        assert response.status_code == 201
        base_key = f"no-soup-for-you/buildsense/storage/{repo.customer_id}/{repo.id}/{user.api_id}/{run_id}"
        pants_log_obj = self._get_s3_object(f"{base_key}/pants_run_log.txt")
        log_compressed = pants_log_obj["Body"].read()  # type: ignore[index]
        assert (
            zlib.decompress(log_compressed)
            == b"How can I go on a cruise with out my cabana wear?\nI love those, those clothes."
        )
        assert pants_log_obj["ContentType"] == "text/plain"  # type: ignore[index]
        assert pants_log_obj["Metadata"] == {"compression": "zlib"}  # type: ignore[index]


class TestBuildsenseConfigView(BaseViewsApiTest):
    def test_get_config(self, client, user: ToolchainUser, repo: Repo) -> None:
        response = client.options(self._get_ingestion_url(repo))
        assert response.status_code == 200
        assert response.json() == {
            "config": {
                "work_units": {
                    "artifacts": ["stdout", "stderr", "xml_results"],
                    "metadata": [
                        "exit_code",
                        "definition",
                        "source",
                        "address",
                        "addresses",
                        "action_digest",
                        "environment_type",
                        "environment_name",
                    ],
                },
                "ci_capture": {
                    "CIRCLECI": r"^CIRCLE.*",
                    "TRAVIS": r"^TRAVIS.*",
                    "GITHUB_ACTIONS": r"^GITHUB.*",
                    "BITBUCKET_BUILD_NUMBER": r"^BITBUCKET.*",
                    "BUILDKITE": r"^BUILDKITE.*",
                },
            },
            "ci_capture": {
                "CIRCLECI": r"^CIRCLE.*",
                "TRAVIS": r"^TRAVIS.*",
                "GITHUB_ACTIONS": r"^GITHUB.*",
                "BITBUCKET_BUILD_NUMBER": r"^BITBUCKET.*",
                "BUILDKITE": r"^BUILDKITE.*",
            },
        }
