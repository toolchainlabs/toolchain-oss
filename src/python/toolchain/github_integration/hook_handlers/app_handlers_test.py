# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json
import re

import pytest

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.site.models import Customer, Repo
from toolchain.github_integration.common.records import GitHubEvent
from toolchain.github_integration.hook_handlers.app_handlers import handle_github_app_event
from toolchain.github_integration.models import ConfigureGithubRepo, GithubRepo
from toolchain.github_integration.test_utils.fixtures_loader import load_fixture
from toolchain.util.test.util import assert_messages


def load_github_event(fixture_name: str) -> GitHubEvent:
    fixture = load_fixture(fixture_name)
    headers = fixture["headers"]
    headers.update(
        {"X-GitHub-Delivery": "I find tinsel distracting", "X-Hub-Signature-256": "You think you are better than me?"}
    )

    return GitHubEvent.create(headers=headers, body=json.dumps(fixture["payload"]).encode())


def add_get_github_org_info_response(httpx_mock, slug: str, fixture_name: str) -> None:
    fixture = load_fixture(fixture_name)
    fixture["login"] = slug
    httpx_mock.add_response(
        method="GET",
        url=f"https://api.github.com/users/{slug}",
        status_code=200,
        json=fixture,
    )


def assert_get_org_info_request(request, slug: str) -> None:
    assert request.url == f"https://api.github.com/users/{slug}"
    assert request.method == "GET"


@pytest.mark.django_db()
class TestAppInstallEvents:
    def _assert_github_repo(self, customer: Customer, repo: GithubRepo) -> None:
        now = utcnow()
        assert repo.repo_id == "82342866"
        assert repo.name == "binhost"
        assert repo.customer_id == customer.pk
        assert repo.install_id == "7382407"
        assert repo.state == GithubRepo.State.ACTIVE
        assert repo.webhook_id == ""
        assert len(repo.webhooks_secret) == 64
        assert repo.created_at.timestamp() == pytest.approx(now.timestamp())
        assert ConfigureGithubRepo.objects.filter(repo_id=repo.id).count() == 1

    def _assert_new_customer_log_message(self, caplog) -> None:
        count = sum(1 for record in caplog.records if re.search("new_customer_created", record.message))
        assert count == 1, "invalid number of new_customer_created log messages (there should be one)"

    def test_install_app_created(self, caplog) -> None:
        assert GithubRepo.objects.count() == 0
        customer = Customer.create(slug="toolchainlabs", name="Feats of Strength")
        assert customer.logo_url == ""
        result = handle_github_app_event(load_github_event("installation_created_selected_repos"))
        assert result is True
        self._assert_new_customer_log_message(caplog)
        assert Repo.objects.count() == 1
        repo = Repo.objects.first()
        assert GithubRepo.objects.count() == 1
        gh_repo = GithubRepo.objects.first()
        self._assert_github_repo(customer, gh_repo)
        assert repo.name == "toolchainlabs/binhost"
        assert repo.slug == "binhost"
        assert repo.customer_id == customer.pk
        assert ConfigureGithubRepo.objects.count() == 1
        loaded_customer = Customer.for_slug("toolchainlabs")
        assert loaded_customer is not None
        assert loaded_customer.logo_url == "https://avatars0.githubusercontent.com/u/35751794?v=4"

    def test_install_app_reactivate_active(self) -> None:
        assert GithubRepo.objects.count() == 0
        customer = Customer.create(slug="toolchainlabs", name="Feats of Strength")
        GithubRepo.activate_or_create(repo_id="82342866", install_id="11111", repo_name="pole", customer_id=customer.pk)
        result = handle_github_app_event(load_github_event("installation_created_selected_repos"))
        assert result is True
        assert GithubRepo.objects.count() == 1
        repo = GithubRepo.objects.first()
        self._assert_github_repo(customer, repo)
        assert ConfigureGithubRepo.objects.count() == 1

    def test_install_app_reactivate_inactive(self) -> None:
        assert GithubRepo.objects.count() == 0
        customer = Customer.create(slug="toolchainlabs", name="Feats of Strength")
        assert customer.logo_url == ""
        repo = GithubRepo.activate_or_create(
            repo_id="82342866", install_id="11111", repo_name="pole", customer_id=customer.pk
        )
        repo.deactivate()
        assert GithubRepo.objects.first().state == GithubRepo.State.INACTIVE
        result = handle_github_app_event(load_github_event("installation_created_selected_repos"))
        assert result is True
        assert GithubRepo.objects.count() == 1
        repo = GithubRepo.objects.first()
        self._assert_github_repo(customer, repo)
        assert ConfigureGithubRepo.objects.count() == 1
        loaded_customer = Customer.for_slug("toolchainlabs")
        assert loaded_customer is not None
        assert loaded_customer.logo_url == "https://avatars0.githubusercontent.com/u/35751794?v=4"

    def test_install_app_reactivate_switch_customers(self) -> None:
        assert GithubRepo.objects.count() == 0
        customer_1 = Customer.create(slug="festivus", name="Tinesl inc")
        Customer.create(slug="toolchainlabs", name="Toolchain")
        GithubRepo.activate_or_create(
            repo_id="82342866", install_id="7382407", repo_name="binhost", customer_id=customer_1.pk
        )
        event = load_github_event("installation_created_selected_repos")
        with pytest.raises(ToolchainAssertion, match=r"GithubRepo.*moved between customers"):
            handle_github_app_event(event)

    def test_delete_app_install(self) -> None:
        customer = Customer.create(slug="toolchainlabs", name="Toolchain")
        GithubRepo.activate_or_create(
            repo_id="82342866", install_id="7382407", repo_name="binhost", customer_id=customer.pk
        )
        assert GithubRepo.objects.first().state == GithubRepo.State.ACTIVE
        result = handle_github_app_event(load_github_event("installation_deleted"))
        assert result is True
        assert GithubRepo.objects.count() == 1
        assert GithubRepo.objects.first().state == GithubRepo.State.INACTIVE
        assert ConfigureGithubRepo.objects.count() == 0

    def test_delete_app_install_missing_customer(self) -> None:
        customer = Customer.create(slug="tinsel", name="Toolchain")
        GithubRepo.activate_or_create(
            repo_id="82342866", install_id="7382407", repo_name="binhost", customer_id=customer.pk
        )
        result = handle_github_app_event(load_github_event("installation_deleted"))
        assert result is False
        assert GithubRepo.objects.count() == 1
        assert GithubRepo.objects.first().state == GithubRepo.State.ACTIVE
        assert ConfigureGithubRepo.objects.count() == 0

    def test_install_app_slug_exists_on_different_customer(self) -> None:
        assert GithubRepo.objects.count() == 0
        Customer.create(slug="toolchainlabs", name="Feats of Strength")
        customer_2 = Customer.create(slug="seinfeld", name="Happy Festivus")
        Repo.create("binhost", customer_2, name="No soup for you")
        result = handle_github_app_event(load_github_event("installation_created_selected_repos"))
        assert result is True
        assert GithubRepo.objects.count() == 1
        assert ConfigureGithubRepo.objects.count() == 1
        assert Repo.objects.count() == 2

    def test_install_app_slug_exists(self) -> None:
        assert GithubRepo.objects.count() == 0
        customer = Customer.create(slug="toolchainlabs", name="Feats of Strength")
        Repo.create("binhost", customer, name="No soup for you")
        result = handle_github_app_event(load_github_event("installation_created_selected_repos"))
        assert result is True
        assert GithubRepo.objects.count() == 1
        assert ConfigureGithubRepo.objects.count() == 1
        assert Repo.objects.count() == 1

    def test_install_app_slug_exists_but_deactivated(self) -> None:
        assert GithubRepo.objects.count() == 0
        customer = Customer.create(slug="toolchainlabs", name="Feats of Strength")
        Repo.create("binhost", customer, name="No soup for you").deactivate()
        result = handle_github_app_event(load_github_event("installation_created_selected_repos"))
        assert result is False
        assert GithubRepo.objects.count() == 0
        assert ConfigureGithubRepo.objects.count() == 0
        assert Repo.objects.count() == 1

    def test_install_app_unknown_action(self, caplog) -> None:
        event = load_github_event("installation_created_selected_repos")
        event.json_payload["action"] = "serenety_now"
        assert handle_github_app_event(event) is False
        assert GithubRepo.objects.count() == 0
        assert ConfigureGithubRepo.objects.count() == 0
        assert_messages(caplog, "unknown install action")

    @pytest.mark.xfail(reason="disabled self service onboarding", strict=True, raises=AssertionError)
    def test_install_app_no_customer_self_service_onboarding(self, httpx_mock, caplog) -> None:
        assert GithubRepo.objects.count() == 0
        assert Customer.objects.count() == 0
        add_get_github_org_info_response(httpx_mock, slug="toolchainlabs", fixture_name="github_api_org_url_1")
        result = handle_github_app_event(load_github_event("installation_created_selected_repos"))
        self._assert_new_customer_log_message(caplog)
        assert result is True
        req = httpx_mock.get_request()
        assert_get_org_info_request(req, slug="toolchainlabs")
        assert Repo.objects.count() == 1
        repo = Repo.objects.first()
        assert Customer.objects.count() == 1
        customer = Customer.objects.first()
        assert customer.slug == "toolchainlabs"
        assert customer.name == "Google"
        assert customer.logo_url == "https://avatars0.githubusercontent.com/u/35751794?v=4"
        assert repo.customer_id == customer.id
        assert GithubRepo.objects.count() == 1
        gh_repo = GithubRepo.objects.first()
        self._assert_github_repo(customer, gh_repo)
        assert repo.name == "toolchainlabs/binhost"
        assert repo.slug == "binhost"
        assert repo.customer_id == customer.pk
        assert ConfigureGithubRepo.objects.count() == 1

    def test_install_app_no_customer_self_service_onboarding_not_github_org(self) -> None:
        assert GithubRepo.objects.count() == 0
        assert Customer.objects.count() == 0
        event = load_github_event("installation_created_selected_repos")
        event.json_payload["installation"]["account"]["type"] = "User"
        result = handle_github_app_event(event)
        assert result is False

    @pytest.mark.xfail(reason="disabled self service onboarding", strict=True, raises=AssertionError)
    def test_install_app_no_customer_self_service_onboarding_no_name_org(self, httpx_mock, caplog) -> None:
        assert GithubRepo.objects.count() == 0
        assert Customer.objects.count() == 0
        add_get_github_org_info_response(httpx_mock, slug="deletorious-antelope", fixture_name="no_name_org")
        result = handle_github_app_event(load_github_event("app_install_self_service"))
        self._assert_new_customer_log_message(caplog)
        assert result is True
        req = httpx_mock.get_request()
        assert_get_org_info_request(req, slug="deletorious-antelope")
        assert Repo.objects.count() == 1
        repo = Repo.objects.first()
        assert Customer.objects.count() == 1
        customer = Customer.objects.first()
        assert customer.slug == "deletorious-antelope"
        assert customer.name == "deletorious-antelope"
        assert customer.logo_url == "https://avatars.githubusercontent.com/u/108426677?v=4"
        assert repo.customer_id == customer.id
        assert GithubRepo.objects.count() == 1
        gh_repo = GithubRepo.objects.first()
        now = utcnow()
        assert gh_repo.repo_id == "509134485"
        assert gh_repo.name == "example-python"
        assert gh_repo.customer_id == customer.pk
        assert gh_repo.install_id == "27000286"
        assert gh_repo.state == GithubRepo.State.ACTIVE
        assert gh_repo.webhook_id == ""
        assert len(gh_repo.webhooks_secret) == 64
        assert gh_repo.created_at.timestamp() == pytest.approx(now.timestamp())
        assert ConfigureGithubRepo.objects.filter(repo_id=gh_repo.id).count() == 1
        assert repo.name == "deletorious-antelope/example-python"
        assert repo.slug == "example-python"
        assert repo.customer_id == customer.pk
        assert ConfigureGithubRepo.objects.count() == 1

    @pytest.mark.parametrize("fixture_name", ["github_app_install_suspend_event", "github_app_install_unsuspend_event"])
    def test_install_app_ignored_events(self, fixture_name: str, caplog) -> None:
        result = handle_github_app_event(load_github_event(fixture_name))
        assert result is False
        assert_messages(caplog, r"Ignored \w*suspend for dupuyfred \(User\)")


@pytest.mark.django_db()
class TestRepoInstallEvents:
    @pytest.fixture()
    def customer(self) -> Customer:
        # we don't match customer names on deactivation
        return Customer.create(slug="jerry", name="Feats of Strength")

    def test_install_repo_removed(self, customer: Customer) -> None:
        repo_1 = GithubRepo.activate_or_create(
            install_id="7382407", repo_id="82342866", repo_name="bazel-buildfarm", customer_id=customer.pk
        )
        repo_2 = GithubRepo.activate_or_create(
            install_id="7382407", repo_id="12342833", repo_name="summer-of-george", customer_id=customer.pk
        )
        assert repo_1.state == GithubRepo.State.ACTIVE
        result = handle_github_app_event(load_github_event("installation_repositories_removed"))
        assert GithubRepo.objects.get(id=repo_1.id).state == GithubRepo.State.INACTIVE
        assert GithubRepo.objects.get(id=repo_2.id).state == GithubRepo.State.ACTIVE
        assert result is True
        assert ConfigureGithubRepo.objects.count() == 1

    def test_install_repo_removed_invalid_install_id(self, customer: Customer) -> None:
        repo_1 = GithubRepo.activate_or_create(
            install_id="7382307111", repo_id="82342866", repo_name="bazel-buildfarm", customer_id=customer.pk
        )
        repo_2 = GithubRepo.activate_or_create(
            install_id="7382407", repo_id="12342833", repo_name="summer-of-george", customer_id=customer.pk
        )
        assert repo_1.state == GithubRepo.State.ACTIVE
        result = handle_github_app_event(load_github_event("installation_repositories_removed"))
        assert result is False
        assert GithubRepo.objects.get(id=repo_1.id).state == GithubRepo.State.ACTIVE
        assert GithubRepo.objects.get(id=repo_2.id).state == GithubRepo.State.ACTIVE
        assert ConfigureGithubRepo.objects.count() == 0

    def test_install_repo_inactivate_customer(self) -> None:
        customer = Customer.create(slug="toolchainlabs", name="fake toolchain")
        customer.deactivate()
        result = handle_github_app_event(load_github_event("installation_repositories_added"))
        assert result is False
        assert ConfigureGithubRepo.objects.count() == 0
        assert Repo.objects.count() == 0


@pytest.mark.django_db()
class TestAppAuthEvents:
    def test_reveoke_app_no_customer(self) -> None:
        result = handle_github_app_event(load_github_event("github_app_authorization_event"))
        assert result is False

    def test_reveoke_app_invalid_github_account_type(self) -> None:
        Customer.create(slug="chrisjrn-tcob", name="Feats of Strength")
        result = handle_github_app_event(load_github_event("github_app_authorization_event"))
        assert result is False

    def test_reveoke_app_invalid_scm_customer_type(self) -> None:
        Customer.create(slug="chrisjrn-tcob", name="Feats of Strength", scm=Customer.Scm.BITBUCKET)
        event = load_github_event("github_app_authorization_event")
        event.json_payload["sender"]["type"] = "Organization"
        result = handle_github_app_event(event)
        assert result is False

    def test_reveoke_app_customer(self) -> None:
        Customer.create(slug="chrisjrn-tcob", name="Feats of Strength")
        event = load_github_event("github_app_authorization_event")
        event.json_payload["sender"]["type"] = "Organization"
        result = handle_github_app_event(event)
        assert result is True
