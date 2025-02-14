# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json

import pytest
from django.core.cache import cache
from freezegun import freeze_time
from moto import mock_s3

from toolchain.aws.s3 import S3
from toolchain.aws.test_utils.s3_utils import assert_bucket_empty, create_s3_bucket
from toolchain.django.site.models import Customer, Repo
from toolchain.github_integration.app_client_test import add_get_workflow_run_response, add_install_token_response
from toolchain.github_integration.client.repo_clients_test import (
    load_as_github_event,
    load_fixture,
    load_fixture_payload,
)
from toolchain.github_integration.models import ConfigureGithubRepo, GithubRepo
from toolchain.github_integration.repo_data_store import GithubRepoDataStore


@pytest.mark.django_db()
class BaseInternalApiTests:
    _BUCKET = "fake-scm-integration-bucket"

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_s3():
            create_s3_bucket(self._BUCKET)
            yield

    def create_repos(self, customer_id: str, repo_id: str):
        customer = Customer.objects.create(id=customer_id, name="Kramerica Industries", slug="cosmo")
        repo = Repo.objects.create(id=repo_id, name="Darren", slug="darren", customer_id=customer_id)
        GithubRepo.activate_or_create(repo_id="bob", install_id="983", repo_name=repo.slug, customer_id=customer.id)


class TestPullRequestView(BaseInternalApiTests):
    def test_get_pr(self, client) -> None:
        self.create_repos("kramer", "ovaltine")
        fixture = load_fixture_payload("pull_request_synchronize")
        S3().upload_json_str(
            bucket=self._BUCKET,
            key="lloyd/braun/pull_request/kramer/ovaltine/0005002.json",
            json_str=json.dumps(fixture),
        )
        response = client.get("/api/v1/github/kramer/ovaltine/pull_requests/5002/")
        assert response.status_code == 200
        assert response.json() == {"pull_request_data": fixture["pull_request"]}
        assert "lloyd/braun/pull_request/kramer/ovaltine/0005002.json" in cache

    def test_get_pr_from_cache(self, client) -> None:
        self.create_repos("kramer", "ovaltine")
        fixture = load_fixture_payload("pull_request_synchronize")
        cache.set(key="lloyd/braun/pull_request/kramer/ovaltine/0005002.json", value=json.dumps(fixture))
        response = client.get("/api/v1/github/kramer/ovaltine/pull_requests/5002/")
        assert response.status_code == 200
        assert response.json() == {"pull_request_data": fixture["pull_request"]}

    def test_get_non_existent_pr(self, client) -> None:
        self.create_repos("cosmo", "jerry")
        response = client.get("/api/v1/github/cosmo/jerry/pull_requests/8822/")
        assert response.status_code == 404
        assert response.content == b'{"detail":"Not found."}'


@pytest.mark.django_db()
class TestCommitView(BaseInternalApiTests):
    def test_get_commit_nested_branch(self, client) -> None:
        self.create_repos("kramer", "ovaltine")
        fixture = load_fixture_payload("repo_push_nested_branch")
        S3().upload_json_str(
            bucket=self._BUCKET,
            key="lloyd/braun/push/kramer/ovaltine/jerry/seinfeld/newman/7aabbeeccc.json",
            json_str=json.dumps(fixture),
        )
        response = client.get("/api/v1/github/kramer/ovaltine/commit/jerry/seinfeld/newman/7aabbeeccc/")
        assert response.status_code == 200
        assert response.json() == {"commit_data": fixture["head_commit"]}

    def test_get_non_existent_commit(self, client) -> None:
        self.create_repos("kramer", "ovaltine")
        response = client.get("/api/v1/github/kramer/ovaltine/commit/jerry/seinfeld/newman/7aabbeeccc/")
        assert response.status_code == 404
        assert response.content == b'{"detail":"Not found."}'

    def test_get_commit_named_branch(self, client) -> None:
        fixture = load_fixture_payload("repo_push_branch_name")
        github_repo_id = fixture["repository"]["id"]
        customer = Customer.create(slug="pantsbuild", name="Jerry Seinfeld")
        repo = Repo.create(slug="pants", customer=customer, name="pantsbuild/pants")
        GithubRepo.activate_or_create(
            repo_id=github_repo_id, install_id="11111", repo_name="pants", customer_id=customer.pk
        )
        store = GithubRepoDataStore.for_github_repo_id(github_repo_id)
        assert store is not None
        store.save_push(fixture)
        response = client.get(
            f"/api/v1/github/{customer.id}/{repo.id}/commit/test-remote-cache/a9ee30ce636f79f302d849b222155ba26afa0208/"
        )
        assert response.status_code == 200
        assert response.json() == {"commit_data": fixture["head_commit"]}


class TestPushView(BaseInternalApiTests):
    def test_get_push_nested_branch(self, client) -> None:
        self.create_repos("kramer", "ovaltine")
        fixture = load_fixture_payload("repo_push_nested_branch")
        S3().upload_json_str(
            bucket=self._BUCKET,
            key="lloyd/braun/push/kramer/ovaltine/jerry/seinfeld/newman/7aabbeeccc.json",
            json_str=json.dumps(fixture),
        )
        response = client.get("/api/v1/github/kramer/ovaltine/push/jerry/seinfeld/newman/7aabbeeccc/")
        assert response.status_code == 200
        del fixture["organization"]
        del fixture["repository"]
        assert response.json() == {"push_data": fixture}

    def test_get_non_existent_push(self, client) -> None:
        self.create_repos("kramer", "ovaltine")
        response = client.get("/api/v1/github/kramer/ovaltine/push/jerry/seinfeld/newman/7aabbeeccc/")
        assert response.status_code == 404
        assert response.content == b'{"detail":"Not found."}'

    def test_get_push_named_branch(self, client) -> None:
        fixture = load_fixture_payload("repo_push_branch_name")
        github_repo_id = fixture["repository"]["id"]
        customer = Customer.create(slug="pantsbuild", name="Jerry Seinfeld")
        repo = Repo.create(slug="pants", customer=customer, name="pantsbuild/pants")
        GithubRepo.activate_or_create(
            repo_id=github_repo_id, install_id="11111", repo_name="pants", customer_id=customer.pk
        )
        store = GithubRepoDataStore.for_github_repo_id(github_repo_id)
        assert store is not None
        store.save_push(fixture)
        response = client.get(
            f"/api/v1/github/{customer.id}/{repo.id}/push/test-remote-cache/a9ee30ce636f79f302d849b222155ba26afa0208/"
        )
        assert response.status_code == 200
        del fixture["organization"]
        del fixture["repository"]
        assert response.json() == {"push_data": fixture}


@pytest.mark.django_db()
class TestRepoWebhookView:
    _BUCKET = "fake-scm-integration-bucket"

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_s3():
            create_s3_bucket(self._BUCKET)
            yield

    def test_get_repo_secret(self, client) -> None:
        repo = GithubRepo.activate_or_create(
            repo_id="87711", install_id="99111", repo_name="tinsel", customer_id="festivus"
        )

        response = client.get("/api/v1/github/hooks/repos/87711/")
        assert response.status_code == 200
        assert response.json() == {
            "repo": {"name": "tinsel", "secret": repo.webhooks_secret},
        }

    def test_get_repo_secret_inactive_repo(self, client) -> None:
        repo = GithubRepo.activate_or_create(
            repo_id="87711", install_id="99111", repo_name="tinsel", customer_id="festivus"
        )
        repo.deactivate()
        response = client.get("/api/v1/github/hooks/repos/87711/")
        assert response.status_code == 404
        assert response.content == b'{"detail":"Not found."}'

    def test_get_repo_secret_no_secret(self, client) -> None:
        repo = GithubRepo.activate_or_create(
            repo_id="87711", install_id="99111", repo_name="tinsel", customer_id="festivus"
        )
        repo.webhooks_secret = ""
        repo.save()
        response = client.get("/api/v1/github/hooks/repos/87711/")
        assert response.status_code == 404
        assert response.content == b'{"detail":"Not found."}'

    def test_get_repo_secret_no_repo(self, client) -> None:
        response = client.get("/api/v1/github/hooks/repos/948504/")
        assert response.status_code == 404
        assert response.content == b'{"detail":"Not found."}'

    def test_post_webhook_missing_repo(self, client) -> None:
        response = client.post(
            "/api/v1/github/hooks/repos/948504/",
            content_type="application/json",
            data=load_as_github_event("pull_request_synchronize"),
        )
        assert response.status_code == 200
        assert response.json() == {"handled": False}
        keys_iter = S3().key_metadata_with_prefix(bucket=self._BUCKET, key_prefix="")
        assert not list(keys_iter)

    def test_post_pull_request_webhook_handled(self, client) -> None:
        customer = Customer.create(slug="toolchainlabs", name="Feats of Strength")
        repo = Repo.create(slug="tinsel", customer=customer, name="Tinel-Distracting")
        GithubRepo.activate_or_create(
            repo_id="51405305", install_id="99111", repo_name="tinsel", customer_id=customer.pk
        )
        response = client.post(
            "/api/v1/github/hooks/repos/51405305/",
            content_type="application/json",
            data=load_as_github_event("pull_request_opened"),
        )
        assert response.status_code == 201
        assert response.json() == {"handled": True}
        s3 = S3()
        key = f"lloyd/braun/pull_request/{repo.customer_id}/{repo.id}/0005769.json"
        assert s3.exists(bucket=self._BUCKET, key=key) is True
        assert key in cache

    def test_post_issue_webhook(self, client) -> None:
        customer = Customer.create(slug="toolchainlabs", name="Feats of Strength")
        repo = Repo.create(slug="tinsel", customer=customer, name="Tinel-Distracting")
        GithubRepo.activate_or_create(
            repo_id="51405305", install_id="99111", repo_name="tinsel", customer_id=customer.pk
        )
        response = client.post(
            "/api/v1/github/hooks/repos/51405305/",
            content_type="application/json",
            data=load_as_github_event("repo_reopen_issue"),
        )
        assert response.status_code == 201
        assert response.json() == {"handled": True}
        s3 = S3()
        key = f"lloyd/braun/pull_request/{repo.customer_id}/{repo.id}/0012828.json"
        assert s3.exists(bucket=self._BUCKET, key=key) is True
        assert key not in cache

    def test_post_issue_webhook_no_repo(self, client) -> None:
        response = client.post(
            "/api/v1/github/hooks/repos/51405305/",
            content_type="application/json",
            data=load_as_github_event("repo_reopen_issue"),
        )
        assert response.status_code == 200
        assert response.json() == {"handled": False}
        assert_bucket_empty(S3(), bucket_name=self._BUCKET)


@pytest.mark.django_db()
class TestAppWebhookView:
    # Full tests for handling app webhook are in app_handlers_test.py
    def test_post_install_app_created(self, client) -> None:
        assert GithubRepo.objects.count() == 0
        customer = Customer.create(slug="toolchainlabs", name="Feats of Strength")
        response = client.post(
            "/api/v1/github/hooks/app/",
            content_type="application/json",
            data=load_as_github_event("installation_created_selected_repos"),
        )
        assert response.status_code == 201
        assert response.json() == {"handled": True}
        assert GithubRepo.objects.count() == 1
        assert ConfigureGithubRepo.objects.count() == 1
        repo = GithubRepo.objects.first()
        assert repo.repo_id == "82342866"
        assert repo.name == "binhost"
        assert repo.customer_id == customer.pk
        assert repo.install_id == "7382407"


@pytest.mark.django_db()
class BaseTestCIResolveView:
    _BUCKET = "fake-scm-integration-bucket"

    @pytest.fixture()
    def repo(self) -> Repo:
        customer = Customer.create(slug="toolchainlabs", name="Feats of Strength")
        return Repo.create(slug="tinsel", customer=customer, name="Tinel-Distracting")

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_s3():
            create_s3_bucket(self._BUCKET)
            yield


class TestCIResolveViewGithubActions(BaseTestCIResolveView):
    @pytest.fixture()
    def github_repo(self, repo: Repo) -> GithubRepo:
        return GithubRepo.activate_or_create(
            repo_id="51405305", install_id="998837373", repo_name=repo.slug, customer_id=repo.customer_id
        )

    def _prep_ci_build(
        self,
        httpx_mock,
        repo: Repo,
        github_repo: GithubRepo,
        run_id: str,
        workflow_run_fixture: str | dict | None = None,
        pr_fixture: str | None = None,
    ) -> None:
        if httpx_mock:
            add_get_workflow_run_response(
                httpx_mock, fixture=workflow_run_fixture, run_id=run_id, repo_fn=f"{repo.customer.slug}/{repo.slug}"
            )
            add_install_token_response(httpx_mock, install_id=github_repo.install_id)
        if pr_fixture:
            pull_request_data = load_fixture_payload(pr_fixture)
            pr_num = pull_request_data["number"]
            S3().upload_json_str(
                bucket=self._BUCKET,
                key=f"lloyd/braun/pull_request/{repo.customer_id}/{repo.pk}/{pr_num}.json",
                json_str=json.dumps(pull_request_data),
            )

    def test_resolve_ci(self, httpx_mock, client, repo: Repo, github_repo: GithubRepo) -> None:
        fixture = load_fixture("get_workflow_run_response")
        fixture["status"] = "in_progress"
        self._prep_ci_build(
            httpx_mock,
            repo,
            github_repo,
            run_id="621923665",
            workflow_run_fixture=fixture,
            pr_fixture="public_pull_request",
        )
        data = {
            "started_treshold_sec": 60 * 6,  # 6m
            "ci_env": {
                "GITHUB_ACTIONS": "true",
                "GITHUB_RUN_ID": "621923665",
                "GITHUB_REF": "refs/pull/12/merge",
                "GITHUB_EVENT_NAME": "pull_request",
                "GITHUB_SHA": "puffy-shirt",
            },
        }
        response = client.post(
            f"/api/v1/github/{repo.customer_id}/{repo.pk}/ci/", data=data, content_type="application/json"
        )
        assert response.status_code == 200
        assert response.json() == {
            "user_id": 1268088,
            "labels": [],
            "key": "gha_2180491069_621923665",
            "ci_link": "https://github.com/toolchainlabs/toolchain/actions/runs/621923665",
            "pr_number": "12",
        }

    def test_resolve_ci_inactive_repo(self, client, repo: Repo, github_repo: GithubRepo) -> None:
        github_repo.deactivate()
        fixture = load_fixture("get_workflow_run_response")
        fixture["status"] = "in_progress"
        self._prep_ci_build(
            httpx_mock=None,
            repo=repo,
            github_repo=github_repo,
            run_id="621923665",
            workflow_run_fixture=fixture,
            pr_fixture="public_pull_request",
        )
        data = {
            "started_treshold_sec": 60 * 6,  # 6m
            "ci_env": {
                "GITHUB_ACTIONS": "true",
                "GITHUB_RUN_ID": "621923665",
                "GITHUB_REF": "refs/pull/12/merge",
                "GITHUB_EVENT_NAME": "pull_request",
                "GITHUB_SHA": "puffy-shirt",
            },
        }
        response = client.post(
            f"/api/v1/github/{repo.customer_id}/{repo.pk}/ci/", data=data, content_type="application/json"
        )
        assert response.status_code == 401
        assert response.json() == {"error": "No GithubRepo for tinsel"}

    def test_resolve_ci_key_too_long(self, httpx_mock, client, repo: Repo, github_repo: GithubRepo) -> None:
        fixture = load_fixture("get_workflow_run_response")
        fixture.update(status="in_progress", check_suite_id=888888838738838838383838, id=44444442222222243636366363)
        self._prep_ci_build(
            httpx_mock,
            repo=repo,
            github_repo=github_repo,
            run_id="44444442222222243636366363",
            workflow_run_fixture=fixture,
            pr_fixture="public_pull_request",
        )
        data = {
            "started_treshold_sec": 60 * 6,  # 6m
            "ci_env": {
                "GITHUB_ACTIONS": "true",
                "GITHUB_RUN_ID": "44444442222222243636366363",
                "GITHUB_REF": "refs/pull/12/merge",
                "GITHUB_EVENT_NAME": "pull_request",
                "GITHUB_SHA": "puffy-shirt",
            },
        }
        response = client.post(
            f"/api/v1/github/{repo.customer_id}/{repo.pk}/ci/", data=data, content_type="application/json"
        )
        assert response.status_code == 401
        assert response.json() == {"error": "Invalid build key"}

    def test_resolve_ci_fail_no_github_pr_info(self, httpx_mock, client, repo: Repo, github_repo: GithubRepo) -> None:
        fixture = load_fixture("get_workflow_run_response")
        fixture["status"] = "in_progress"
        self._prep_ci_build(
            httpx_mock,
            repo=repo,
            github_repo=github_repo,
            run_id="621923665",
            workflow_run_fixture=fixture,
            pr_fixture="public_pull_request",
        )
        data = {
            "started_treshold_sec": 60 * 6,  # 6m
            "ci_env": {
                "GITHUB_ACTIONS": "true",
                "GITHUB_RUN_ID": "621923665",
                "GITHUB_REF": "refs/pull/773/merge",
                "GITHUB_EVENT_NAME": "pull_request",
                "GITHUB_SHA": "puffy-shirt",
            },
        }
        response = client.post(
            f"/api/v1/github/{repo.customer_id}/{repo.pk}/ci/", data=data, content_type="application/json"
        )
        assert response.status_code == 401
        assert response.json() == {"error": "ci=github_actions Missing PR info"}

    def test_resolve_ci_fail_unknown_run_id(self, httpx_mock, client, repo: Repo, github_repo: GithubRepo) -> None:
        self._prep_ci_build(
            httpx_mock, repo=repo, github_repo=github_repo, run_id="621923665", workflow_run_fixture=None
        )
        data = {
            "started_treshold_sec": 60 * 6,  # 6m
            "ci_env": {
                "GITHUB_ACTIONS": "true",
                "GITHUB_RUN_ID": "621923665",
                "GITHUB_REF": "refs/pull/773/merge",
                "GITHUB_EVENT_NAME": "pull_request",
                "GITHUB_SHA": "puffy-shirt",
            },
        }
        response = client.post(
            f"/api/v1/github/{repo.customer_id}/{repo.pk}/ci/", data=data, content_type="application/json"
        )
        assert response.status_code == 401
        assert response.json() == {
            "error": "ci=github_actions Unknown run_id='621923665' repo=<Repo: Tinel-Distracting>"
        }

    def test_resolve_ci_run_id_mismatch(self, httpx_mock, client, repo: Repo, github_repo: GithubRepo) -> None:
        fixture = load_fixture("get_workflow_run_response")
        fixture.update(status="in_progress", id=883332)
        self._prep_ci_build(
            httpx_mock,
            repo=repo,
            github_repo=github_repo,
            run_id="621923665",
            workflow_run_fixture=fixture,
            pr_fixture="public_pull_request",
        )
        data = {
            "started_treshold_sec": 60 * 6,  # 6m
            "ci_env": {
                "GITHUB_ACTIONS": "true",
                "GITHUB_RUN_ID": "621923665",
                "GITHUB_REF": "refs/pull/12/merge",
                "GITHUB_EVENT_NAME": "pull_request",
                "GITHUB_SHA": "puffy-shirt",
            },
        }
        response = client.post(
            f"/api/v1/github/{repo.customer_id}/{repo.pk}/ci/", data=data, content_type="application/json"
        )
        assert response.status_code == 401
        assert response.json() == {
            "error": "ci=github_actions run_id mismatch run_id='621923665' workflow_run_id=883332"
        }

    def test_resolve_ci_fail_pr_parsing_error(self, httpx_mock, client, repo: Repo, github_repo: GithubRepo) -> None:
        fixture = load_fixture("get_workflow_run_response")
        fixture["status"] = "in_progress"
        self._prep_ci_build(
            httpx_mock,
            repo=repo,
            github_repo=github_repo,
            run_id="621923665",
            workflow_run_fixture=fixture,
            pr_fixture="public_pull_request",
        )
        data = {
            "started_treshold_sec": 60 * 6,  # 6m
            "ci_env": {
                "GITHUB_ACTIONS": "true",
                "GITHUB_RUN_ID": "621923665",
                "GITHUB_REF": "refs/head/shirt/merge",
                "GITHUB_EVENT_NAME": "pull_request",
                "GITHUB_SHA": "puffy-shirt",
            },
        }
        response = client.post(
            f"/api/v1/github/{repo.customer_id}/{repo.pk}/ci/", data=data, content_type="application/json"
        )
        assert response.status_code == 401
        assert response.json() == {
            "error": "ci=github_actions Can't parse PR number github_ref='refs/head/shirt/merge' run_id='621923665'"
        }

    def test_resolve_ci_fail_not_pull_request_event_env(self, client, repo: Repo, github_repo: GithubRepo) -> None:
        fixture = load_fixture("get_workflow_run_response")
        fixture["status"] = "in_progress"
        self._prep_ci_build(
            httpx_mock=None,
            repo=repo,
            github_repo=github_repo,
            run_id="621923665",
            workflow_run_fixture=fixture,
            pr_fixture="public_pull_request",
        )
        data = {
            "started_treshold_sec": 60 * 6,  # 6m
            "ci_env": {
                "GITHUB_ACTIONS": "true",
                "GITHUB_RUN_ID": "2008080037",
                "GITHUB_REF": "refs/head/puffy",
                "GITHUB_EVENT_NAME": "push",
                "GITHUB_SHA": "puffy-shirt",
            },
        }
        response = client.post(
            f"/api/v1/github/{repo.customer_id}/{repo.pk}/ci/", data=data, content_type="application/json"
        )

        assert response.status_code == 401
        assert response.json() == {
            "error": "ci=github_actions Invalid event_name='push' run_id='2008080037' repo=<Repo: Tinel-Distracting>"
        }

    def test_resolve_ci_fail_not_pull_request_event_workflow_run(
        self, httpx_mock, client, repo: Repo, github_repo: GithubRepo
    ) -> None:
        fixture = load_fixture("get_workflow_run_response")
        fixture.update(status="in_progress", event="push")
        self._prep_ci_build(
            httpx_mock,
            repo=repo,
            github_repo=github_repo,
            run_id="621923665",
            workflow_run_fixture=fixture,
            pr_fixture="public_pull_request",
        )
        data = {
            "started_treshold_sec": 60 * 6,  # 6m
            "ci_env": {
                "GITHUB_ACTIONS": "true",
                "GITHUB_RUN_ID": "621923665",
                "GITHUB_REF": "refs/pull/12/merge",
                "GITHUB_EVENT_NAME": "pull_request",
                "GITHUB_SHA": "puffy-shirt",
            },
        }
        response = client.post(
            f"/api/v1/github/{repo.customer_id}/{repo.pk}/ci/", data=data, content_type="application/json"
        )

        assert response.status_code == 401
        assert response.json() == {"error": "ci=github_actions Invalid event type event=push run_id='621923665'"}

    @freeze_time(datetime.datetime(2021, 3, 1, 22, 1, tzinfo=datetime.timezone.utc))
    def test_resolve_ci_fail_build_status(self, httpx_mock, client, repo: Repo, github_repo: GithubRepo) -> None:
        self._prep_ci_build(
            httpx_mock,
            repo=repo,
            github_repo=github_repo,
            run_id="621923665",
            workflow_run_fixture="get_workflow_run_response",
            pr_fixture="public_pull_request",
        )
        data = {
            "started_treshold_sec": 60 * 6,  # 6m
            "ci_env": {
                "GITHUB_ACTIONS": "true",
                "GITHUB_RUN_ID": "621923665",
                "GITHUB_REF": "refs/pull/12/merge",
                "GITHUB_EVENT_NAME": "pull_request",
                "GITHUB_SHA": "puffy-shirt",
            },
        }
        response = client.post(
            f"/api/v1/github/{repo.customer_id}/{repo.pk}/ci/", data=data, content_type="application/json"
        )
        assert response.status_code == 401
        assert response.json() == {"error": "ci=github_actions Invalid build status=completed run_id='621923665'"}

    @pytest.mark.parametrize(
        "missing",
        [
            ("GITHUB_RUN_ID", "GITHUB_EVENT_NAME"),
            ("GITHUB_REF", "GITHUB_EVENT_NAME"),
            ("GITHUB_SHA", "GITHUB_EVENT_NAME"),
            ("GITHUB_RUN_ID", "GITHUB_SHA"),
            ("GITHUB_SHA",),
            ("GITHUB_EVENT_NAME",),
            ("GITHUB_REF",),
        ],
    )
    def test_resolve_ci_missing_env_vars(
        self, missing: tuple[str, ...], client, repo: Repo, github_repo: GithubRepo
    ) -> None:
        fixture = load_fixture("get_workflow_run_response")
        fixture["status"] = "in_progress"
        self._prep_ci_build(
            httpx_mock=None,
            repo=repo,
            github_repo=github_repo,
            run_id="621923665",
            workflow_run_fixture=fixture,
            pr_fixture="public_pull_request",
        )
        data = {
            "started_treshold_sec": 60 * 6,  # 6m
            "ci_env": {
                "GITHUB_ACTIONS": "true",
                "GITHUB_RUN_ID": "621923665",
                "GITHUB_REF": "refs/pull/12/merge",
                "GITHUB_EVENT_NAME": "pull_request",
                "GITHUB_SHA": "puffy-shirt",
            },
        }
        for env_var in missing:
            del data["ci_env"][env_var]  # type: ignore[attr-defined]

        response = client.post(
            f"/api/v1/github/{repo.customer_id}/{repo.pk}/ci/", data=data, content_type="application/json"
        )
        assert response.status_code == 401
        assert response.json() == {"error": f"ci=github_actions Missing environment variables: {sorted(missing)}"}

    def test_resolve_ci_githb_server_error_on_get_token(
        self, httpx_mock, client, repo: Repo, github_repo: GithubRepo
    ) -> None:
        httpx_mock.add_response(
            method="POST",
            url=f"https://api.github.com/app/installations/{github_repo.install_id}/access_tokens",
            status_code=503,
            content="I choose not to run.",
        )
        data = {
            "started_treshold_sec": 60 * 6,  # 6m
            "ci_env": {
                "GITHUB_ACTIONS": "true",
                "GITHUB_RUN_ID": "621923665",
                "GITHUB_REF": "refs/pull/12/merge",
                "GITHUB_EVENT_NAME": "pull_request",
                "GITHUB_SHA": "puffy-shirt",
            },
        }
        response = client.post(
            f"/api/v1/github/{repo.customer_id}/{repo.pk}/ci/", data=data, content_type="application/json"
        )
        assert response.status_code == 401
        assert response.json() == {"error": "ci=github_actions github_server_error"}

    def test_resolve_ci_githb_server_error_on_get_workflow(
        self, httpx_mock, client, repo: Repo, github_repo: GithubRepo
    ) -> None:
        add_install_token_response(httpx_mock, install_id=github_repo.install_id)
        httpx_mock.add_response(
            method="GET",
            url=f"https://api.github.com/repos/{repo.customer.slug}/{repo.slug}/actions/runs/621923665",
            status_code=500,
            content="I choose not to run.",
        )
        data = {
            "started_treshold_sec": 60 * 6,  # 6m
            "ci_env": {
                "GITHUB_ACTIONS": "true",
                "GITHUB_RUN_ID": "621923665",
                "GITHUB_REF": "refs/pull/12/merge",
                "GITHUB_EVENT_NAME": "pull_request",
                "GITHUB_SHA": "puffy-shirt",
            },
        }
        response = client.post(
            f"/api/v1/github/{repo.customer_id}/{repo.pk}/ci/", data=data, content_type="application/json"
        )
        assert response.status_code == 401
        assert response.json() == {"error": "ci=github_actions github_server_error"}


@pytest.mark.django_db()
class TestCustomerRepoView:
    def _create_repos(self, customer_id: str) -> None:
        with freeze_time(datetime.datetime(2020, 11, 2, 16, 3, tzinfo=datetime.timezone.utc)):
            GithubRepo.activate_or_create(repo_id="11111", install_id="31", repo_name="tinsel", customer_id=customer_id)

            GithubRepo.activate_or_create(
                repo_id="33399", install_id="11", repo_name="distracting", customer_id="frank"
            )
            GithubRepo.activate_or_create(repo_id="22222", install_id="22", repo_name="pole", customer_id=customer_id)
        GithubRepo.activate_or_create(repo_id="11111", install_id="31", repo_name="nobagel", customer_id=customer_id)

    def test_get_repos(self, client) -> None:
        self._create_repos("festivus")
        GithubRepo.get_by_github_repo_id("11111").deactivate()  # type: ignore[union-attr]
        response = client.get("/api/v1/github/festivus/")
        assert response.status_code == 200
        assert response.json() == {
            "results": [
                {"created_at": "2020-11-02T16:03:00+00:00", "name": "nobagel", "state": "inactive", "repo_id": "11111"},
                {"created_at": "2020-11-02T16:03:00+00:00", "name": "pole", "state": "active", "repo_id": "22222"},
            ]
        }

    def test_get_repos_options_no_customer(self, client) -> None:
        response = client.options("/api/v1/github/festivus/")
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found."}

    def test_get_repos_options(self, client) -> None:
        customer = Customer.create("chocolate", "Chocolate Babka")
        self._create_repos(customer.pk)
        response = client.options(f"/api/v1/github/{customer.id}/")
        assert response.status_code == 200
        assert response.json() == {
            "data": {
                "install_link": "https://seinfeld.jerry.com/installations/new",
                "install_id": "31",
                "configure_link": "https://github.com/organizations/chocolate/settings/installations/31",
            }
        }

    def test_get_repos_options_no_repos(self, client) -> None:
        customer = Customer.create("chocolate", "Chocolate Babka")
        self._create_repos("jerry")
        response = client.options(f"/api/v1/github/{customer.id}/")
        assert response.status_code == 200
        assert response.json() == {
            "data": {
                "install_link": "https://seinfeld.jerry.com/installations/new",
            }
        }
