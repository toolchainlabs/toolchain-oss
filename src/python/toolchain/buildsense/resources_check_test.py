# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import boto3
import pytest
from moto import mock_dynamodb, mock_s3

from toolchain.aws.test_utils.s3_utils import create_s3_bucket
from toolchain.buildsense.ingestion.run_info_table import RunInfoTable
from toolchain.django.site.models import Customer, Repo, ToolchainUser
from toolchain.util.influxdb.mock_metrics_store import mock_rest_client
from toolchain.util.test.elastic_search_util import DummyElasticRequests


@pytest.mark.django_db()
class TestDependentResourcesCheckz:
    _BUCKET = "fake-test-buildsense-bucket"

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_dynamodb(), mock_s3():
            create_s3_bucket(self._BUCKET)
            RunInfoTable.create_table()
            yield

    @pytest.fixture()
    def mock_client(self):
        with mock_rest_client() as mock_client:
            yield mock_client

    @pytest.fixture()
    def customer(self) -> Customer:
        return Customer.create(slug="acmeid", name="acme")

    @pytest.fixture()
    def repo(self, customer: Customer) -> Repo:
        return Repo.create("acmebotid", customer=customer, name="acmebot")

    @pytest.fixture(autouse=True)
    def user(self, customer: Customer) -> ToolchainUser:
        user = ToolchainUser.create(username="kramer", email="kramer@jerrysplace.com")
        customer.add_user(user)
        return user

    def _call_check(self, client, mock_client) -> dict:
        mock_client.add_ping_response()
        DummyElasticRequests.add_response("GET", "/", json_body={"jerry": "You can’t over-dry."})
        DummyElasticRequests.add_response(
            "GET", "/buildsense/_stats", json_body={"kramer": "You're a rabid anti-dentite!"}
        )
        response = client.get("/checksz/resourcez")
        assert response.status_code == 200
        request = mock_client.get_request()
        assert request.url == "http://jerry.festivus:9911/ping"
        return response.json()

    def test_empty(self, client, mock_client, user: ToolchainUser, customer: Customer, repo: Repo):
        resp_json = self._call_check(client, mock_client)
        assert resp_json == {
            "users_db": {"Customer": customer.pk, "Repo": repo.pk, "ToolchainUser": user.pk},
            "buildsense_db": {"ProcessPantsRun": 0},
            "dynamodb": {"run_info_table": 0},
            "s3": {"dummy_key": 0},
            "influxdb": True,
            "opensearch": {
                "domain": {"jerry": "You can’t over-dry."},
                "stats": {"kramer": "You're a rabid anti-dentite!"},
            },
        }

    def test_dependent_resources_check_view(
        self, client, mock_client, user: ToolchainUser, customer: Customer, repo: Repo
    ):
        boto3.client("s3").put_object(
            Bucket=self._BUCKET,
            Key=f"no-soup-for-you/buildsense/storage/{customer.pk}/{repo.pk}/jerry.txt",
            Body="But I don't want to be a pirate!",
        )
        resp_json = self._call_check(client, mock_client)
        assert resp_json == {
            "users_db": {"Customer": customer.pk, "Repo": repo.pk, "ToolchainUser": user.pk},
            "buildsense_db": {"ProcessPantsRun": 0},
            "dynamodb": {"run_info_table": 0},
            "s3": {f"no-soup-for-you/buildsense/storage/{customer.pk}/{repo.pk}/jerry.txt": 32},
            "influxdb": True,
            "opensearch": {
                "domain": {"jerry": "You can’t over-dry."},
                "stats": {"kramer": "You're a rabid anti-dentite!"},
            },
        }
