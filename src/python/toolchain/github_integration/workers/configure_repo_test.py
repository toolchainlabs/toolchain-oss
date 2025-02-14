# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json

import pytest

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.site.models import Customer, Repo
from toolchain.github_integration.app_client_test import (
    add_install_token_response,
    add_install_token_response_no_permissions,
)
from toolchain.github_integration.models import ConfigureGithubRepo, GithubRepo
from toolchain.github_integration.test_utils.fixtures_loader import load_fixture
from toolchain.github_integration.workers.configure_repo import GithubRepoConfigurator
from toolchain.github_integration.workers.dispatcher import GithubIntegrationWorkDispatcher
from toolchain.workflow.models import WorkUnit
from toolchain.workflow.tests_helper import BaseWorkflowWorkerTests


@pytest.mark.django_db()
class BaseGithubWorkflowTests(BaseWorkflowWorkerTests):
    def get_dispatcher(self) -> type[GithubIntegrationWorkDispatcher]:
        return GithubIntegrationWorkDispatcher


class TestGithubRepoConfigurator(BaseGithubWorkflowTests):
    @pytest.fixture()
    def customer(self) -> Customer:
        return Customer.create(slug="ovaltine", name="Ovaltine!")

    @pytest.fixture()
    def repo(self, customer: Customer) -> Repo:
        return Repo.create(slug="tinsel", name="Festivus for the rest of us", customer=customer)

    @pytest.fixture()
    def github_repo(self, customer: Customer, repo: Repo) -> GithubRepo:
        return GithubRepo.activate_or_create(
            install_id="65544", repo_id="8833", repo_name=repo.slug, customer_id=customer.pk
        )

    def _add_list_webhooks_response(self, httpx_mock, *tc_webhook_events: str, url: str | None = None) -> None:
        fixture: list[dict] = load_fixture("list_webhooks_response")  # type: ignore[assignment]
        if tc_webhook_events:
            fixture.append(
                {
                    "active": True,
                    "config": {"url": url or "http://hooks.jerry.com/dave/repo"},
                    "created_at": "2020-02-17T20:23:45Z",
                    "events": list(tc_webhook_events),
                    "id": 88272,
                    "type": "Repository",
                    "updated_at": "2020-05-14T00:08:22Z",
                }
            )
        httpx_mock.add_response(method="GET", url="https://api.github.com/repos/ovaltine/tinsel/hooks", json=fixture)

    def _add_empty_list_webhooks_response(self, httpx_mock) -> None:
        httpx_mock.add_response(method="GET", url="https://api.github.com/repos/ovaltine/tinsel/hooks", json=[])

    def assert_state(self, state: str) -> None:
        assert ConfigureGithubRepo.objects.count() == 1
        wu = ConfigureGithubRepo.objects.first().work_unit
        assert wu.state == state

    def test_unknown_repo(self) -> None:
        payload = ConfigureGithubRepo.create("bosco")
        worker = GithubRepoConfigurator()
        with pytest.raises(ToolchainAssertion, match="Unknown GithubRepo: bosco"):
            worker.do_work(payload)

    def test_create_webhook_no_hooks(self, httpx_mock, github_repo: GithubRepo) -> None:
        add_install_token_response(httpx_mock, "65544")
        self._add_empty_list_webhooks_response(httpx_mock)
        httpx_mock.add_response(
            method="POST",
            url="https://api.github.com/repos/ovaltine/tinsel/hooks",
            json=load_fixture("create_webhook_response"),
        )
        ConfigureGithubRepo.create(github_repo.id)
        assert self.do_work() == 1
        self.assert_state(WorkUnit.SUCCEEDED)
        requests = httpx_mock.get_requests()
        assert len(requests) == 3
        request = requests[-1]
        assert request.method == "POST"
        assert request.url == "https://api.github.com/repos/ovaltine/tinsel/hooks"
        assert json.loads(request.read()) == {
            "active": True,
            "name": "web",
            "events": ["pull_request", "push", "create", "check_run"],
            "config": {
                "url": "http://newman.jerry.com/dave/repo",
                "content_type": "json",
                "secret": github_repo.webhooks_secret,
                "insecure_ssl": 0,
            },
        }

    def test_create_webhook_other_hooks(self, httpx_mock, github_repo: GithubRepo) -> None:
        add_install_token_response(httpx_mock, "65544")
        self._add_list_webhooks_response(httpx_mock)
        httpx_mock.add_response(
            method="POST",
            url="https://api.github.com/repos/ovaltine/tinsel/hooks",
            json=load_fixture("create_webhook_response"),
        )
        ConfigureGithubRepo.create(github_repo.id)
        assert self.do_work() == 1
        self.assert_state(WorkUnit.SUCCEEDED)
        requests = httpx_mock.get_requests()
        assert len(requests) == 3
        request = requests[-1]
        assert request.method == "POST"
        assert request.url == "https://api.github.com/repos/ovaltine/tinsel/hooks"
        assert json.loads(request.read()) == {
            "active": True,
            "name": "web",
            "events": ["pull_request", "push", "create", "check_run"],
            "config": {
                "url": "http://newman.jerry.com/dave/repo",
                "content_type": "json",
                "secret": github_repo.webhooks_secret,
                "insecure_ssl": 0,
            },
        }

    def test_delete_webhook_no_hooks(self, httpx_mock, github_repo: GithubRepo, repo: Repo) -> None:
        repo.deactivate()
        add_install_token_response(httpx_mock, "65544")
        self._add_empty_list_webhooks_response(httpx_mock)
        ConfigureGithubRepo.create(github_repo.id)
        assert self.do_work() == 1
        self.assert_state(WorkUnit.SUCCEEDED)
        assert len(httpx_mock.get_requests()) == 2
        assert GithubRepo.objects.get(id=github_repo.id).is_active is False

    def test_delete_webhook_no_toolchain_hooks(self, httpx_mock, github_repo: GithubRepo, repo: Repo) -> None:
        repo.deactivate()
        add_install_token_response(httpx_mock, "65544")
        self._add_list_webhooks_response(httpx_mock)
        ConfigureGithubRepo.create(github_repo.id)
        assert self.do_work() == 1
        self.assert_state(WorkUnit.SUCCEEDED)
        assert len(httpx_mock.get_requests()) == 2
        assert GithubRepo.objects.get(id=github_repo.id).is_active is False

    def test_delete_webhook(self, httpx_mock, github_repo: GithubRepo, repo: Repo) -> None:
        repo.deactivate()
        add_install_token_response(httpx_mock, "65544")
        self._add_list_webhooks_response(httpx_mock, "bob", "cobb")
        httpx_mock.add_response(method="DELETE", url="https://api.github.com/repos/ovaltine/tinsel/hooks/88272")
        ConfigureGithubRepo.create(github_repo.id)
        assert self.do_work() == 1
        self.assert_state(WorkUnit.SUCCEEDED)
        requests = httpx_mock.get_requests()
        assert len(requests) == 3
        request = requests[-1]
        assert request.method == "DELETE"
        assert request.url == "https://api.github.com/repos/ovaltine/tinsel/hooks/88272"
        assert GithubRepo.objects.get(id=github_repo.id).is_active is False

    def test_delete_webhook_inactive_customer(
        self, httpx_mock, github_repo: GithubRepo, repo: Repo, customer: Customer
    ) -> None:
        customer.deactivate()
        repo.deactivate()
        add_install_token_response(httpx_mock, "65544")
        self._add_list_webhooks_response(httpx_mock, "bob", "cobb")
        httpx_mock.add_response(method="DELETE", url="https://api.github.com/repos/ovaltine/tinsel/hooks/88272")
        ConfigureGithubRepo.create(github_repo.id)
        assert self.do_work() == 1
        self.assert_state(WorkUnit.SUCCEEDED)
        requests = httpx_mock.get_requests()
        assert len(requests) == 3
        request = requests[-1]
        assert request.method == "DELETE"
        assert request.url == "https://api.github.com/repos/ovaltine/tinsel/hooks/88272"
        assert GithubRepo.objects.get(id=github_repo.id).is_active is False

    def test_update_webhook(self, httpx_mock, github_repo: GithubRepo) -> None:
        add_install_token_response(httpx_mock, "65544")
        self._add_list_webhooks_response(httpx_mock, "tinsel", "festivus")
        httpx_mock.add_response(
            method="PATCH",
            url="https://api.github.com/repos/ovaltine/tinsel/hooks/88272",
            json=load_fixture("create_webhook_response"),
        )

        ConfigureGithubRepo.create(github_repo.id)
        assert self.do_work() == 1
        self.assert_state(WorkUnit.SUCCEEDED)
        requests = httpx_mock.get_requests()
        assert len(requests) == 3
        request = requests[-1]
        assert request.method == "PATCH"
        assert request.url == "https://api.github.com/repos/ovaltine/tinsel/hooks/88272"
        assert json.loads(request.read()) == {
            "active": True,
            "events": ["pull_request", "push", "create", "check_run"],
            "config": {
                "url": "http://newman.jerry.com/dave/repo",
                "content_type": "json",
                "secret": github_repo.webhooks_secret,
                "insecure_ssl": 0,
            },
        }

    def test_update_webhook_extra_events(self, httpx_mock, github_repo: GithubRepo) -> None:
        add_install_token_response(httpx_mock, "65544")
        self._add_list_webhooks_response(httpx_mock, "tinsel", "festivus")
        httpx_mock.add_response(
            method="PATCH",
            url="https://api.github.com/repos/ovaltine/tinsel/hooks/88272",
            json=load_fixture("create_webhook_response"),
        )

        cfg = ConfigureGithubRepo.create(github_repo.id)
        cfg._extra_events = "soup,chicken,jerry"
        cfg.save()
        assert self.do_work() == 1
        self.assert_state(WorkUnit.SUCCEEDED)
        requests = httpx_mock.get_requests()
        assert len(requests) == 3
        request = requests[-1]
        assert request.method == "PATCH"
        assert request.url == "https://api.github.com/repos/ovaltine/tinsel/hooks/88272"
        assert json.loads(request.read()) == {
            "active": True,
            "events": ["pull_request", "push", "create", "check_run", "soup", "chicken", "jerry"],
            "config": {
                "url": "http://newman.jerry.com/dave/repo",
                "content_type": "json",
                "secret": github_repo.webhooks_secret,
                "insecure_ssl": 0,
            },
        }

    def test_update_webhook_no_op(self, httpx_mock, github_repo: GithubRepo) -> None:
        add_install_token_response(httpx_mock, "65544")
        self._add_list_webhooks_response(
            httpx_mock, "pull_request", "push", "create", "check_run", url="http://newman.jerry.com/dave/repo"
        )
        ConfigureGithubRepo.create(github_repo.id)
        assert self.do_work() == 1
        self.assert_state(WorkUnit.SUCCEEDED)
        requests = httpx_mock.get_requests()
        assert len(requests) == 2  # get token, list webhooks

    def test_update_webhook_force(self, httpx_mock, github_repo: GithubRepo) -> None:
        add_install_token_response(httpx_mock, "65544")
        self._add_list_webhooks_response(
            httpx_mock, "pull_request", "push", "create", "check_run", url="http://newman.jerry.com/dave/repo"
        )
        httpx_mock.add_response(
            method="PATCH",
            url="https://api.github.com/repos/ovaltine/tinsel/hooks/88272",
            json=load_fixture("create_webhook_response"),
        )
        cgr = ConfigureGithubRepo.create(github_repo.id)
        cgr.force_update = True
        cgr.save()
        assert self.do_work() == 1
        self.assert_state(WorkUnit.SUCCEEDED)
        requests = httpx_mock.get_requests()
        assert len(requests) == 3
        request = requests[-1]
        assert request.method == "PATCH"
        assert request.url == "https://api.github.com/repos/ovaltine/tinsel/hooks/88272"
        assert json.loads(request.read()) == {
            "active": True,
            "events": ["pull_request", "push", "create", "check_run"],
            "config": {
                "url": "http://newman.jerry.com/dave/repo",
                "content_type": "json",
                "secret": github_repo.webhooks_secret,
                "insecure_ssl": 0,
            },
        }
        assert ConfigureGithubRepo.objects.count() == 1
        assert ConfigureGithubRepo.objects.first().force_update is False

    def test_disconect_repo_no_access(self, httpx_mock, github_repo: GithubRepo, repo: Repo) -> None:
        repo.deactivate()
        add_install_token_response_no_permissions(httpx_mock, "65544")
        ConfigureGithubRepo.create(github_repo.id)
        assert self.do_work() == 1
        self.assert_state(WorkUnit.SUCCEEDED)
        assert len(httpx_mock.get_requests()) == 1
        assert GithubRepo.objects.get(id=github_repo.id).is_active is False
