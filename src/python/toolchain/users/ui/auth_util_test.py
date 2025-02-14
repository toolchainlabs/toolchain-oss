# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
from unittest import mock

import pkg_resources
import pytest
from requests.exceptions import ReadTimeout
from social_core.exceptions import AuthAlreadyAssociated, AuthForbidden

from toolchain.base.datetime_tools import utcnow
from toolchain.django.auth.constants import AccessTokenAudience
from toolchain.django.site.auth.toolchain_bitbucket import ToolchainBitbucketOAuth2
from toolchain.django.site.auth.toolchain_github import ToolchainGithubOAuth2
from toolchain.django.site.models import Customer, ToolchainUser
from toolchain.django.site.test_helpers.models_helpers import create_github_user
from toolchain.users.models import AuthProvider, OptionalBool, UserAuth, UserCustomerAccessConfig
from toolchain.users.ui.auth_util import check_is_user_allowed, create_user, load_user, update_user_details
from toolchain.util.test.util import assert_messages


def load_fixture(fixture_name: str) -> dict:
    return json.loads(pkg_resources.resource_string(__name__, f"fixtures/{fixture_name}.json"))


def assert_get_org_admins(responses, org_slugs: tuple[str, ...]) -> None:
    assert len(responses.calls) == len(org_slugs)
    for idx, call in enumerate(responses.calls):
        slug = org_slugs[idx]
        assert call.request.method == "GET"
        assert call.request.url == f"https://api.github.com/orgs/{slug}/members?role=admin&per_page=100"
        assert call.request.headers["Authorization"] == "token h&h-bagles"


def add_org_admins(responses, org_slugs: tuple[str, ...]) -> None:
    org_admins = load_fixture("github_org_admins")
    for org_slug in org_slugs:
        responses.add(
            responses.GET,
            url=f"https://api.github.com/orgs/{org_slug}/members?role=admin&per_page=100",
            json=org_admins,
        )


@pytest.mark.django_db()
class BaseUpdateUserDetailsTests:
    PROVIDER = AuthProvider.GITHUB

    def _assert_rw_user(self, user: ToolchainUser, customer: Customer, is_admin: bool = False) -> None:
        assert UserCustomerAccessConfig.objects.count() == 1
        expected_audience = (
            AccessTokenAudience.FRONTEND_API
            | AccessTokenAudience.BUILDSENSE_API
            | AccessTokenAudience.CACHE_RW
            | AccessTokenAudience.CACHE_RO
        )
        if is_admin:
            expected_audience |= AccessTokenAudience.IMPERSONATE
        assert (
            UserCustomerAccessConfig.get_audiences_for_user(customer_id=customer.id, user_api_id=user.api_id)
            == expected_audience
        )
        uac = UserCustomerAccessConfig.objects.first()
        assert uac.allowed_audiences == expected_audience
        assert uac.is_admin == is_admin
        expected_role = UserCustomerAccessConfig.Role.ORG_ADMIN if is_admin else UserCustomerAccessConfig.Role.USER
        assert uac.role == expected_role

    def _assert_user_auth(
        self,
        user: ToolchainUser,
        user_id: str,
        username: str,
        emails: tuple[str, ...] = tuple(),
    ) -> None:
        assert UserAuth.objects.count() == 1
        user_auth = UserAuth.objects.first()
        assert user_auth.provider == self.PROVIDER
        assert user_auth.user_id == user_id
        assert user_auth.user_api_id == user.api_id
        assert user_auth.username == username
        assert user_auth.email_addresses == emails


class TestUpdateUserDetailsGithub(BaseUpdateUserDetailsTests):
    @pytest.fixture()
    def github_backend(self) -> ToolchainGithubOAuth2:
        req = mock.MagicMock()
        return ToolchainGithubOAuth2.for_request(req, redirect_uri="")

    def test_update_user_details_new_user(self, github_backend: ToolchainGithubOAuth2) -> None:
        user = ToolchainUser.create(username="kramer", email="kramer@soup.com")
        response = {
            "avatar_url": "http://jerry.com/picture.jpg",
            "html_url": "http://jerry.net/kramer",
            "id": 8374982,
            "login": "jambalaya",
        }
        update_user_details(
            github_backend, user, response, {"fullname": "Cosmo Kramer", "username": "jambalaya"}, False
        )
        user = ToolchainUser.get_by_api_id(user.api_id)  # reload user from DB
        assert user.avatar_url == "http://jerry.com/picture.jpg"
        self._assert_user_auth(user, "8374982", username="jambalaya")

    def test_update_user_details_new_user_email_allowed(self, github_backend: ToolchainGithubOAuth2) -> None:
        user = ToolchainUser.create(username="kramer", email="kramer@soup.com")
        response = {
            "avatar_url": "http://jerry.com/picture.jpg",
            "html_url": "http://jerry.net/kramer",
            "name": "Cosmo",
            "id": 8374982,
            "login": "jambalaya",
            "email_allowed": True,
        }
        update_user_details(
            github_backend, user, response, {"fullname": "Cosmo Kramer", "username": "jambalaya"}, False
        )
        user = ToolchainUser.get_by_api_id(user.api_id)  # reload user from DB
        assert user.avatar_url == "http://jerry.com/picture.jpg"
        assert user.full_name == user.get_full_name() == "Cosmo Kramer"
        assert UserCustomerAccessConfig.objects.count() == 0
        self._assert_user_auth(user, "8374982", username="jambalaya")

    def test_update_user_change_github_id_in_user_auth(self, github_backend: ToolchainGithubOAuth2) -> None:
        user_1 = ToolchainUser.create(username="kramer", email="kramer@soup.com")
        user_2 = ToolchainUser.create(username="jerry", email="jerry@soup.com")
        UserAuth.update_or_create(
            user=user_1, provider=AuthProvider.GITHUB, user_id="7663311", username="cosmo", emails=["kramer@nyc.com"]
        )
        response = {
            "avatar_url": "http://jerry.com/picture.jpg",
            "html_url": "http://jerry.net/kramer",
            "id": 7663311,
            "login": "soup",
        }
        with pytest.raises(AuthAlreadyAssociated, match="This account is already in use."):
            update_user_details(
                github_backend, user_2, response, {"fullname": "Jerry Seinfeld", "username": "soup"}, False
            )
        assert UserCustomerAccessConfig.objects.count() == 0
        self._assert_user_auth(user_1, "7663311", username="cosmo", emails=("kramer@nyc.com",))

    def test_dont_update_user_details(self) -> None:
        user = ToolchainUser.create(username="kramer", email="kramer@soup.com")
        mock_gitlab_backend = mock.MagicMock()
        mock_gitlab_backend.name = "gitlab"
        response = {"avatar_url": "http://jerry.com/picture.jpg", "html_url": "http://jerry.net/kramer", "id": 998821}
        update_user_details(
            mock_gitlab_backend, user, response, {"fullname": "Cosmo Kramer", "username": "kramer"}, False
        )
        user = ToolchainUser.get_by_api_id(user.api_id)  # reload user from DB
        assert UserCustomerAccessConfig.objects.count() == 0
        assert UserAuth.objects.count() == 0

    def test_dont_update_user_inactive_user(self, github_backend: ToolchainGithubOAuth2) -> None:
        user = ToolchainUser.create(username="kramer", email="kramer@soup.com")
        user.deactivate()
        response = {
            "avatar_url": "http://jerry.com/picture.jpg",
            "html_url": "http://jerry.net/kramer",
            "id": 832749,
            "login": "pole",
        }
        update_user_details(github_backend, user, response, {"username": "pole"}, False)
        assert ToolchainUser.objects.count() == 1
        user = ToolchainUser.objects.first()  # reload user from DB
        assert user.avatar_url == ""
        assert UserCustomerAccessConfig.objects.count() == 0
        assert UserAuth.objects.count() == 0

    def test_update_user_details_customers(self, responses, github_backend: ToolchainGithubOAuth2) -> None:
        c1 = Customer.create(slug="tinsel", name="I find tinsel distracting")
        c2 = Customer.create(slug="pole", name="feats of strength")
        user = ToolchainUser.create(username="kramer", email="kramer@soup.com")
        add_org_admins(responses, org_slugs=("pole",))
        response = {
            "avatar_url": "http://jerry.com/picture.jpg",
            "html_url": "http://jerry.net/kramer",
            "login": "funny-guy",
            "id": 87833,
            "toolchain_customers": Customer.for_slugs(["pole"]),
            "access_token": "h&h-bagles",
        }
        update_user_details(
            github_backend, user, response, {"fullname": "Cosmo Kramer", "username": "funny-guy"}, False
        )
        user = ToolchainUser.get_by_api_id(user.api_id)  # reload user from DB
        assert user.avatar_url == "http://jerry.com/picture.jpg"
        assert set(c1.users.all()) == set()
        assert set(c2.users.all()) == {user}
        self._assert_rw_user(user, c2)
        self._assert_user_auth(user, "87833", username="funny-guy")
        assert_get_org_admins(responses, org_slugs=("pole",))

    def test_update_user_details_customers_revoke_admin(self, responses, github_backend: ToolchainGithubOAuth2) -> None:
        c1 = Customer.create(slug="tinsel", name="I find tinsel distracting")
        c2 = Customer.create(slug="pole", name="feats of strength")
        user = ToolchainUser.create(username="kramer", email="kramer@soup.com")
        UserCustomerAccessConfig.create_readwrite(
            customer_id=c2.id, user_api_id=user.api_id, is_org_admin=OptionalBool.TRUE
        )
        self._assert_rw_user(user, c2, is_admin=True)  # Sanity check
        add_org_admins(responses, org_slugs=("pole",))
        response = {
            "avatar_url": "http://jerry.com/picture.jpg",
            "html_url": "http://jerry.net/kramer",
            "login": "funny-guy",
            "id": 87833,
            "toolchain_customers": Customer.for_slugs(["pole"]),
            "access_token": "h&h-bagles",
        }
        update_user_details(
            github_backend, user, response, {"fullname": "Cosmo Kramer", "username": "funny-guy"}, False
        )
        user = ToolchainUser.get_by_api_id(user.api_id)  # reload user from DB
        assert user.avatar_url == "http://jerry.com/picture.jpg"
        assert set(c1.users.all()) == set()
        assert set(c2.users.all()) == {user}
        self._assert_rw_user(user, c2, is_admin=False)
        self._assert_user_auth(user, "87833", username="funny-guy")
        assert_get_org_admins(responses, org_slugs=("pole",))

    def test_update_user_details_customers_org_admin(self, responses, github_backend: ToolchainGithubOAuth2) -> None:
        c1 = Customer.create(slug="tinsel", name="I find tinsel distracting")
        c2 = Customer.create(slug="pole", name="feats of strength")
        user = ToolchainUser.create(username="kramer", email="kramer@soup.com")
        add_org_admins(responses, org_slugs=("pole",))
        response = {
            "avatar_url": "http://jerry.com/picture.jpg",
            "html_url": "http://jerry.net/kramer",
            "login": "funny-guy",
            "id": 901363,
            "toolchain_customers": Customer.for_slugs(["pole"]),
            "access_token": "h&h-bagles",
        }
        update_user_details(
            github_backend, user, response, {"fullname": "Cosmo Kramer", "username": "funny-guy"}, False
        )
        user = ToolchainUser.get_by_api_id(user.api_id)  # reload user from DB
        assert user.avatar_url == "http://jerry.com/picture.jpg"
        assert set(c1.users.all()) == set()
        assert set(c2.users.all()) == {user}
        self._assert_rw_user(user, c2, is_admin=True)
        self._assert_user_auth(user, "901363", username="funny-guy")
        assert_get_org_admins(responses, org_slugs=("pole",))

    def test_update_user_details_customers_org_admin_api_fail_network(
        self, responses, github_backend: ToolchainGithubOAuth2
    ) -> None:
        c1 = Customer.create(slug="tinsel", name="I find tinsel distracting")
        user = ToolchainUser.create(username="kramer", email="kramer@soup.com")
        responses.add(
            responses.GET,
            url="https://api.github.com/orgs/tinsel/members?role=admin&per_page=100",
            body=ReadTimeout("No soup for you"),
        )
        response = {
            "avatar_url": "http://jerry.com/picture.jpg",
            "html_url": "http://jerry.net/kramer",
            "login": "funny-guy",
            "id": 901363,
            "toolchain_customers": Customer.for_slugs(["tinsel"]),
            "access_token": "h&h-bagles",
        }
        update_user_details(
            github_backend, user, response, {"fullname": "Cosmo Kramer", "username": "funny-guy"}, False
        )
        user = ToolchainUser.get_by_api_id(user.api_id)  # reload user from DB
        assert user.avatar_url == "http://jerry.com/picture.jpg"

        assert set(c1.users.all()) == {user}
        self._assert_rw_user(user, c1, is_admin=False)
        self._assert_user_auth(user, "901363", username="funny-guy")
        assert_get_org_admins(responses, org_slugs=("tinsel",))

    def test_update_user_details_customers_org_admin_api_fail_http(
        self, responses, github_backend: ToolchainGithubOAuth2
    ) -> None:
        c1 = Customer.create(slug="tinsel", name="I find tinsel distracting")
        user = ToolchainUser.create(username="kramer", email="kramer@soup.com")
        responses.add(
            responses.GET,
            url="https://api.github.com/orgs/tinsel/members?role=admin&per_page=100",
            status=503,
            body=b"Jambalaya",
        )
        response = {
            "avatar_url": "http://jerry.com/picture.jpg",
            "html_url": "http://jerry.net/kramer",
            "login": "funny-guy",
            "id": 901363,
            "toolchain_customers": Customer.for_slugs(["tinsel"]),
            "access_token": "h&h-bagles",
        }
        update_user_details(
            github_backend, user, response, {"fullname": "Cosmo Kramer", "username": "funny-guy"}, False
        )
        user = ToolchainUser.get_by_api_id(user.api_id)  # reload user from DB
        assert user.avatar_url == "http://jerry.com/picture.jpg"

        assert set(c1.users.all()) == {user}
        self._assert_rw_user(user, c1, is_admin=False)
        self._assert_user_auth(user, "901363", username="funny-guy")
        assert_get_org_admins(responses, org_slugs=("tinsel",))

    def test_update_user_details_customers_already_associated(
        self, responses, github_backend: ToolchainGithubOAuth2
    ) -> None:
        assert UserCustomerAccessConfig.objects.count() == 0
        c1 = Customer.create(slug="tinsel", name="I find tinsel distracting")
        c2 = Customer.create(slug="pole", name="feats of strength")
        user = ToolchainUser.create(username="kramer", email="kramer@soup.com")
        c2.add_user(user)
        add_org_admins(responses, org_slugs=("pole",))
        response = {
            "avatar_url": "http://jerry.com/picture.jpg",
            "html_url": "http://jerry.net/kramer",
            "login": "kramer",
            "id": 93898934,
            "toolchain_customers": Customer.for_slugs(["pole"]),
            "access_token": "h&h-bagles",
        }
        update_user_details(github_backend, user, response, {"fullname": "Cosmo Kramer", "username": "kramer"}, False)
        user = ToolchainUser.get_by_api_id(user.api_id)  # reload user from DB
        assert user.avatar_url == "http://jerry.com/picture.jpg"
        assert set(c1.users.all()) == set()
        assert set(c2.users.all()) == {user}
        self._assert_rw_user(user, c2)
        self._assert_user_auth(user, "93898934", username="kramer")
        assert_get_org_admins(responses, org_slugs=("pole",))

    def test_update_user_details_customers_multiple_orgs(
        self, responses, github_backend: ToolchainGithubOAuth2
    ) -> None:
        c1 = Customer.create(slug="tinsel", name="I find tinsel distracting")
        c2 = Customer.create(slug="pole", name="feats of strength")
        c3 = Customer.create(slug="puffy", name="I don't want to be a pirate")
        user = ToolchainUser.create(username="kramer", email="kramer@soup.com")
        UserCustomerAccessConfig.create(
            user_api_id=user.api_id,
            customer_id=c2.pk,
            audience=AccessTokenAudience.FRONTEND_API | AccessTokenAudience.CACHE_RW,
            is_org_admin=False,
        )
        c2.add_user(user)
        add_org_admins(responses, org_slugs=("pole", "puffy"))
        response = {
            "avatar_url": "http://jerry.com/picture.jpg",
            "html_url": "http://jerry.net/kramer",
            "login": "seinfeld",
            "id": 998821,
            "access_token": "h&h-bagles",
            "toolchain_customers": sorted(Customer.for_slugs(["pole", "puffy"]), key=lambda cust: cust.slug),
        }
        update_user_details(github_backend, user, response, {"fullname": "Cosmo Kramer", "username": "seinfeld"}, False)
        user = ToolchainUser.get_by_api_id(user.api_id)  # reload user from DB
        assert user.avatar_url == "http://jerry.com/picture.jpg"
        assert set(c1.users.all()) == set()
        assert set(c2.users.all()) == {user}
        assert set(c3.users.all()) == {user}
        assert UserCustomerAccessConfig.objects.count() == 2
        assert (
            UserCustomerAccessConfig.get_audiences_for_user(user_api_id=user.api_id, customer_id=c2.pk)
            == AccessTokenAudience.FRONTEND_API | AccessTokenAudience.CACHE_RW
        )
        assert (
            UserCustomerAccessConfig.get_audiences_for_user(user_api_id=user.api_id, customer_id=c1.pk)
            == AccessTokenAudience.FRONTEND_API
        )
        self._assert_user_auth(user, "998821", username="seinfeld")
        assert_get_org_admins(responses, org_slugs=("pole", "puffy"))

    def test_update_user_details_update_customer_set(self, responses, github_backend: ToolchainGithubOAuth2) -> None:
        c1 = Customer.create(slug="tinsel", name="I find tinsel distracting")
        c2 = Customer.create(slug="pole", name="feats of strength")
        c3 = Customer.create(slug="puffy", name="I don't want to be a pirate")
        user = ToolchainUser.create(username="kramer", email="kramer@soup.com")
        c2.add_user(user)
        add_org_admins(responses, org_slugs=("puffy", "tinsel"))
        response = {
            "avatar_url": "http://jerry.com/picture.jpg",
            "html_url": "http://jerry.net/kramer",
            "login": "seinfeld",
            "id": 998821,
            "access_token": "h&h-bagles",
            "toolchain_customers": sorted(Customer.for_slugs(["tinsel", "puffy"]), key=lambda cust: cust.slug),
        }
        update_user_details(github_backend, user, response, {"fullname": "Cosmo Kramer", "username": "seinfeld"}, False)
        user = ToolchainUser.get_by_api_id(user.api_id)  # reload user from DB
        assert user.avatar_url == "http://jerry.com/picture.jpg"
        assert set(c1.users.all()) == {user}
        assert set(c2.users.all()) == set()
        assert set(c3.users.all()) == {user}
        assert UserCustomerAccessConfig.objects.count() == 2
        assert (
            UserCustomerAccessConfig.get_audiences_for_user(user_api_id=user.api_id, customer_id=c1.pk)
            == AccessTokenAudience.FRONTEND_API
            | AccessTokenAudience.CACHE_RW
            | AccessTokenAudience.CACHE_RO
            | AccessTokenAudience.BUILDSENSE_API
        )
        assert (
            UserCustomerAccessConfig.get_audiences_for_user(user_api_id=user.api_id, customer_id=c3.pk)
            == AccessTokenAudience.FRONTEND_API
            | AccessTokenAudience.CACHE_RW
            | AccessTokenAudience.CACHE_RO
            | AccessTokenAudience.BUILDSENSE_API
        )
        self._assert_user_auth(user, "998821", username="seinfeld")
        assert_get_org_admins(responses, org_slugs=("puffy", "tinsel"))

    def test_update_user_details_update_customer_set_with_internal(
        self, responses, github_backend: ToolchainGithubOAuth2
    ) -> None:
        c1 = Customer.create(slug="tinsel", name="I find tinsel distracting", customer_type=Customer.Type.INTERNAL)
        c2 = Customer.create(slug="pole", name="feats of strength")
        c3 = Customer.create(slug="puffy", name="I don't want to be a pirate")
        user = ToolchainUser.create(username="kramer", email="kramer@soup.com")
        c2.add_user(user)
        c1.add_user(user)
        add_org_admins(responses, org_slugs=("puffy",))
        response = {
            "avatar_url": "http://jerry.com/picture.jpg",
            "html_url": "http://jerry.net/kramer",
            "login": "seinfeld",
            "id": 998821,
            "access_token": "h&h-bagles",
            "toolchain_customers": sorted(Customer.for_slugs(["puffy"]), key=lambda cust: cust.slug),
        }
        update_user_details(github_backend, user, response, {"fullname": "Cosmo Kramer", "username": "seinfeld"}, False)
        user = ToolchainUser.get_by_api_id(user.api_id)  # reload user from DB
        assert user.avatar_url == "http://jerry.com/picture.jpg"
        assert set(c1.users.all()) == {user}
        assert set(c2.users.all()) == set()
        assert set(c3.users.all()) == {user}
        assert UserCustomerAccessConfig.objects.count() == 1
        assert (
            UserCustomerAccessConfig.get_audiences_for_user(user_api_id=user.api_id, customer_id=c1.pk)
            == AccessTokenAudience.FRONTEND_API
        )
        assert (
            UserCustomerAccessConfig.get_audiences_for_user(user_api_id=user.api_id, customer_id=c3.pk)
            == AccessTokenAudience.FRONTEND_API
            | AccessTokenAudience.CACHE_RW
            | AccessTokenAudience.CACHE_RO
            | AccessTokenAudience.BUILDSENSE_API
        )
        self._assert_user_auth(user, "998821", username="seinfeld")
        assert_get_org_admins(responses, org_slugs=("puffy",))


class TestUpdateUserDetailsBitBucket(BaseUpdateUserDetailsTests):
    PROVIDER = AuthProvider.BITBUCKET

    @pytest.fixture()
    def bitbucket_backend(self) -> ToolchainBitbucketOAuth2:
        req = mock.MagicMock()
        return ToolchainBitbucketOAuth2.for_request(req, redirect_uri="")

    def test_update_user_details_new_user(self, bitbucket_backend) -> None:
        user = ToolchainUser.create(username="jseinfeld", email="jerry@soup.com")
        response = {
            # See toolchain_bitbucket_test.py
            "username": "jerry",
            "display_name": "Jerry Seinfeld",
            "nickname": "Jagdish",
            "organization_names": ("sony",),
            "account_id": "6059303e630024006f000000",
            "uuid": "{6ae3c307-ae59-4135-9c72-ea19ffffffff}",
            "verified_emails": ["jerry@nbc.com", "jerry@nyc.com"],
            "links": {
                "avatar": {"href": "https://jerry.com/pictures/soup.jpg"},
                "html": {"href": "https://bitbucket.org/good-night-jagdish/"},
            },
        }
        result = update_user_details(
            bitbucket_backend, user, response, {"fullname": "Jerry Seinfeld", "username": "jerry"}, False
        )
        user_auth = UserAuth.objects.first()
        assert result == {"social": user_auth.get_social_user()}
        user = ToolchainUser.get_by_api_id(user.api_id)  # reload user from DB
        assert user.avatar_url == "https://jerry.com/pictures/soup.jpg"
        self._assert_user_auth(
            user, "6059303e630024006f000000", username="jerry", emails=("jerry@nbc.com", "jerry@nyc.com")
        )


@pytest.mark.django_db()
class TestLoadUser:
    @pytest.fixture()
    def github_backend(self) -> ToolchainGithubOAuth2:
        req = mock.MagicMock()
        return ToolchainGithubOAuth2.for_request(req, redirect_uri="")

    @pytest.fixture()
    def bitbucket_backend(self) -> ToolchainBitbucketOAuth2:
        req = mock.MagicMock()
        return ToolchainBitbucketOAuth2.for_request(req, redirect_uri="")

    def test_not_github(self, django_assert_num_queries) -> None:
        gitlab_backend = mock.MagicMock()
        gitlab_backend.name = "gitlab"
        with django_assert_num_queries(0):
            result = load_user(gitlab_backend, {}, {})
        assert not result

    def test_load_user_from_user_auth(self, caplog, github_backend: ToolchainGithubOAuth2) -> None:
        user = create_github_user(username="kramer", email="kramer@jerrysplace.com", github_user_id="6544422")
        UserAuth.update_or_create(
            user=user, user_id="6544422", provider=AuthProvider.GITHUB, username="cosmo", emails=["kramer@nbc.com"]
        )
        assert len(caplog.records) == 2
        assert_messages(caplog, r"Created UserAuth user_api_id")
        result = load_user(backend=github_backend, details={"username": "kramer"}, response={"id": 6544422})
        assert result == {
            "uid": 6544422,
            "username": "kramer",
            "user": user,
            "social": UserAuth.objects.first().get_social_user(),
            "is_new": False,
            "new_association": False,
        }
        assert len(caplog.records) == 2

    def test_load_user_from_user_auth_inactive(self, caplog, github_backend: ToolchainGithubOAuth2) -> None:
        user = create_github_user(username="kramer", email="kramer@jerrysplace.com", github_user_id="6544422")
        UserAuth.update_or_create(
            user=user, user_id="6544422", provider=AuthProvider.GITHUB, username="cosmo", emails=["kramer@nbc.com"]
        )
        user.deactivate()
        with pytest.raises(AuthForbidden, match="Your credentials aren't allowed"):
            load_user(backend=github_backend, details={"username": "kramer"}, response={"id": 6544422})
        assert_messages(caplog, r"User not found \(or not active\) for 6544422")

    def test_associate_user_auth_by_email(self, bitbucket_backend: ToolchainBitbucketOAuth2) -> None:
        user = ToolchainUser.create(username="kramer", email="kramer@soup.com")
        social_user, _ = UserAuth.update_or_create(
            user=user,
            provider=AuthProvider.GITHUB,
            user_id="7443322",
            username="cosmo",
            emails=["cosmo@kramer.com", "cosmo@seinfeld.com"],
        )
        response = {
            "verified_emails": ["kramer@nyc.com", "cosmo@seinfeld.com"],
        }
        result = load_user(backend=bitbucket_backend, details={"username": "kramer"}, response=response)
        assert result == {
            "uid": None,
            "username": "kramer",
            "user": user,
            "social": None,
            "is_new": False,
            "new_association": True,
        }


@pytest.mark.django_db()
class TestCheckIsUserAllowed:
    @pytest.fixture()
    def github_backend(self) -> ToolchainGithubOAuth2:
        req = mock.MagicMock()
        return ToolchainGithubOAuth2.for_request(req, redirect_uri="")

    def test_check_is_user_allowed(self, github_backend: ToolchainBitbucketOAuth2) -> None:
        Customer.create(slug="tinsel", name="I find tinsel distracting", scm=Customer.Scm.GITHUB)
        Customer.create(slug="pole", name="feats of strength", scm=Customer.Scm.GITHUB)
        details = {"email": "jerry@kramer.com", "username": "jerry.s"}
        response = {
            "verified_emails": frozenset(("jerry@hello.com",)),
            "login": "jerry",
            "organization_names": frozenset(["puddy", "puffy", "festivus"]),
        }
        check_is_user_allowed(backend=github_backend, details=details, response=response, request=mock.MagicMock())
        assert "toolchain_customers" in response
        toolchain_customers = response["toolchain_customers"]
        assert toolchain_customers == frozenset()


@pytest.mark.django_db()
class TestCreateUser:
    @pytest.fixture()
    def github_backend(self) -> ToolchainGithubOAuth2:
        req = mock.MagicMock()
        return ToolchainGithubOAuth2.for_request(req, redirect_uri="")

    def test_existing_user(self, github_backend: ToolchainGithubOAuth2) -> None:
        details = {"email": "jerry@nyc.com", "username": "jerrys", "fullname": "Jerry Seinfeld"}
        user = create_github_user(username="kramer", email="kramer@jerrysplace.com", github_user_id="6544422")
        response = {
            "verified_emails": frozenset(("jerry@nbc.com", "jerry@nyc.com")),
            "toolchain_customers": [Customer.create(slug="usps", name="US Postal Service")],
            "create_date": datetime.datetime(2018, 1, 22, tzinfo=datetime.timezone.utc),
        }
        result = create_user(
            strategy=github_backend.strategy, details=details, backend=github_backend, user=user, response=response
        )
        assert result == {"is_new": False}

    def test_new_user(self, github_backend: ToolchainGithubOAuth2) -> None:
        details = {"email": "jerry@nyc.com", "username": "jerrys", "fullname": "Jerry Seinfeld"}
        assert ToolchainUser.objects.count() == 0

        customers = [Customer.create(slug="tinsel", name="distracting")]
        response = {"verified_emails": frozenset(("jerry@nbc.com", "jerry@nyc.com")), "toolchain_customers": customers}
        result = create_user(
            strategy=github_backend.strategy,
            details=details,
            backend=github_backend,
            user=None,
            response=response,
        )
        assert ToolchainUser.objects.count() == 1
        user = ToolchainUser.objects.first()
        assert result == {"is_new": True, "user": user}
        assert user.email == "jerry@nbc.com"
        assert user.username == "jerrys"
        assert user.full_name == "Jerry Seinfeld"
        assert user.avatar_url == ""
        assert user.is_active is True

    def test_create_user_existing_username(self, github_backend: ToolchainGithubOAuth2) -> None:
        details = {"email": "jerry@nyc.com", "username": "seinfeld", "fullname": "Jerry Seinfeld"}
        create_github_user(
            username="seinfeld", email="seinfeld@jerrysplace.com", github_username="seinfeld", github_user_id="88338383"
        )
        response = {
            "verified_emails": frozenset(("jerry@nbc.com", "jerry@nyc.com")),
            "toolchain_customers": [Customer.create(slug="usps", name="US Postal Service")],
            "create_date": datetime.datetime(2018, 1, 22, tzinfo=datetime.timezone.utc),
        }
        assert ToolchainUser.objects.count() == 1
        result = create_user(
            strategy=github_backend.strategy, details=details, backend=github_backend, user=None, response=response
        )
        assert ToolchainUser.objects.count() == 2
        new_user = ToolchainUser.objects.get(id=result["user"].id)
        assert result == {"is_new": True, "user": new_user}
        assert new_user.email == "jerry@nbc.com"
        assert new_user.username.startswith("seinfeld-github-")
        assert len(new_user.username) == 21
        assert new_user.username == new_user.username.lower()
        assert new_user.full_name == "Jerry Seinfeld"
        assert new_user.avatar_url == ""
        assert new_user.is_active is True

    def test_create_user_existing_username_different_case(self, github_backend: ToolchainGithubOAuth2) -> None:
        # not handling this properly right now, will have to fix later.
        details = {"email": "jerry@nyc.com", "username": "Seinfeld", "fullname": "Jerry Seinfeld"}
        create_github_user(
            username="seinfeld", email="seinfeld@jerrysplace.com", github_username="seinfeld", github_user_id="88338383"
        )
        customers = [
            Customer.create(slug="tinsel", name="distracting"),
            Customer.create(slug="festivus", name="costanza"),
        ]
        response = {
            "verified_emails": frozenset(("jerry@nbc.com", "jerry@nyc.com")),
            "toolchain_customers": customers,
            "create_date": datetime.datetime(2018, 1, 22, tzinfo=datetime.timezone.utc),
        }
        assert ToolchainUser.objects.count() == 1
        result = create_user(
            strategy=github_backend.strategy, details=details, backend=github_backend, user=None, response=response
        )
        assert ToolchainUser.objects.count() == 2
        new_user = ToolchainUser.objects.get(id=result["user"].id)
        assert result == {"is_new": True, "user": new_user}
        assert new_user.email == "jerry@nbc.com"
        assert new_user.username.startswith("Seinfeld-github-")
        assert len(new_user.username) == 21
        assert new_user.full_name == "Jerry Seinfeld"
        assert new_user.avatar_url == ""
        assert new_user.is_active is True

    @pytest.mark.parametrize("blocked_username", ["me", "ME", "mE"])
    def test_create_user_blocked_username(self, blocked_username: str, github_backend: ToolchainGithubOAuth2) -> None:
        details = {"email": "jerry@nyc.com", "username": blocked_username, "fullname": "Jerry Seinfeld"}
        response = {
            "verified_emails": frozenset(("jerry@nbc.com", "jerry@nyc.com")),
            "toolchain_customers": [Customer.create(slug="usps", name="US Postal Service")],
            "create_date": datetime.datetime(2018, 1, 22, tzinfo=datetime.timezone.utc),
        }
        assert ToolchainUser.objects.count() == 0
        result = create_user(
            strategy=github_backend.strategy, details=details, backend=github_backend, user=None, response=response
        )
        assert ToolchainUser.objects.count() == 1
        new_user = ToolchainUser.objects.first()
        assert result == {"is_new": True, "user": new_user}
        assert new_user.email == "jerry@nbc.com"
        assert new_user.username.startswith(f"{blocked_username}-github-")
        assert len(new_user.username) == 15
        assert new_user.full_name == "Jerry Seinfeld"
        assert new_user.avatar_url == ""
        assert new_user.is_active is True

    def test_create_user_existing_email(self, github_backend: ToolchainGithubOAuth2) -> None:
        details = {"email": "jerry@nyc.com", "username": "jerry", "fullname": "Jerry Seinfeld"}
        create_github_user(
            username="seinfeld", email="jerry@nyc.com", github_username="seinfeld", github_user_id="88338383"
        )
        response = {
            "verified_emails": frozenset(("jerry@nbc.com", "jerry@nyc.com")),
            "toolchain_customers": [Customer.create(slug="usps", name="US Postal Service")],
            "create_date": datetime.datetime(2018, 1, 22, tzinfo=datetime.timezone.utc),
        }
        assert ToolchainUser.objects.count() == 1
        result = create_user(
            strategy=github_backend.strategy,
            details=details,
            backend=github_backend,
            user=None,
            response=response,
        )
        assert ToolchainUser.objects.count() == 2
        new_user = ToolchainUser.objects.get(id=result["user"].id)
        assert result == {"is_new": True, "user": new_user}
        assert new_user.email == "jerry@nbc.com"
        assert new_user.username == "jerry"
        assert new_user.full_name == "Jerry Seinfeld"
        assert new_user.avatar_url == ""
        assert new_user.is_active is True

    def test_create_user_existing_email_emails_no_available_emails(self, github_backend: ToolchainGithubOAuth2) -> None:
        details = {"email": "jerry@nyc.com", "username": "jerry", "fullname": "Jerry Seinfeld"}
        response = {
            "verified_emails": frozenset(("jerry@nbc.com", "jerry@abc.com", "jerry@nyc.com")),
            "toolchain_customers": [Customer.create(slug="usps", name="US Postal Service")],
            "create_date": datetime.datetime(2018, 1, 22, tzinfo=datetime.timezone.utc),
        }
        create_github_user(
            username="seinfeld", email="jerry@nyc.com", github_username="seinfeld", github_user_id="88338383"
        )
        assert ToolchainUser.objects.count() == 1
        result = create_user(
            strategy=github_backend.strategy, details=details, backend=github_backend, user=None, response=response
        )
        assert ToolchainUser.objects.count() == 2
        new_user = ToolchainUser.objects.get(id=result["user"].id)
        assert result == {"is_new": True, "user": new_user}
        assert new_user.email == "jerry@abc.com"
        assert new_user.username == "jerry"
        assert new_user.full_name == "Jerry Seinfeld"
        assert new_user.avatar_url == ""
        assert new_user.is_active is True

    def test_create_user_skip_invalid_email(self, github_backend: ToolchainGithubOAuth2) -> None:
        details = {"email": "jerry@users.noreply.github.com", "username": "jerry", "fullname": "Jerry Seinfeld"}
        # using yoyoma.com since it will when sorted, users.noreply.github.com will be first and will be skipped.
        response = {
            "verified_emails": frozenset(("jerry@users.noreply.github.com", "jerry@yoyoma.com")),
            "toolchain_customers": [Customer.create(slug="usps", name="US Postal Service")],
            "create_date": datetime.datetime(2018, 1, 22, tzinfo=datetime.timezone.utc),
        }
        assert ToolchainUser.objects.count() == 0
        result = create_user(
            strategy=github_backend.strategy,
            details=details,
            backend=github_backend,
            user=None,
            response=response,
        )
        assert ToolchainUser.objects.count() == 1
        new_user = ToolchainUser.objects.get(id=result["user"].id)
        assert result == {"is_new": True, "user": new_user}
        assert new_user.email == "jerry@yoyoma.com"
        assert new_user.username == "jerry"
        assert new_user.full_name == "Jerry Seinfeld"
        assert new_user.avatar_url == ""
        assert new_user.is_active is True

    def test_create_user_prefer_corp_email(self, github_backend: ToolchainGithubOAuth2) -> None:
        details = {"email": "jerry@users.noreply.github.com", "username": "jerry", "fullname": "Jerry Seinfeld"}
        # using yoyoma.com since it will when sorted, users.noreply.github.com, gmail.com will second and both need to be skipped
        response = {
            "verified_emails": frozenset(("jerry@users.noreply.github.com", "jerry@gmail.com", "jerry@yoyoma.com")),
            "toolchain_customers": [Customer.create(slug="usps", name="US Postal Service")],
        }
        assert ToolchainUser.objects.count() == 0
        result = create_user(
            strategy=github_backend.strategy,
            details=details,
            backend=github_backend,
            user=None,
            response=response,
        )
        assert ToolchainUser.objects.count() == 1
        new_user = ToolchainUser.objects.get(id=result["user"].id)
        assert result == {"is_new": True, "user": new_user}
        assert new_user.email == "jerry@yoyoma.com"
        assert new_user.username == "jerry"
        assert new_user.full_name == "Jerry Seinfeld"
        assert new_user.avatar_url == ""
        assert new_user.is_active is True

    def test_corp_email_with_valid_primary_email(self, github_backend: ToolchainGithubOAuth2) -> None:
        details = {"email": "jerry@gmail.com", "username": "Seinfeld", "fullname": "Jerry Seinfeld"}
        customers = [Customer.create(slug="tinsel", name="distracting")]
        response = {
            "verified_emails": frozenset(["jerry.seinfeld@bolor.com", "jerry.s.seinfeld@gmail.com", "jerry@gmail.com"]),
            "toolchain_customers": customers,
        }
        assert ToolchainUser.objects.count() == 0
        result = create_user(
            strategy=github_backend.strategy, details=details, backend=github_backend, user=None, response=response
        )
        assert ToolchainUser.objects.count() == 1
        new_user = ToolchainUser.objects.get(id=result["user"].id)
        assert result == {"is_new": True, "user": new_user}
        assert new_user.email == "jerry.seinfeld@bolor.com"
        assert new_user.username == "Seinfeld"
        assert new_user.full_name == "Jerry Seinfeld"
        assert new_user.avatar_url == ""
        assert new_user.is_active is True

    def test_new_github_user_with_customer_associated(self, github_backend: ToolchainGithubOAuth2) -> None:
        details = {"email": "jerry@gmail.com", "username": "Seinfeld", "fullname": "Jerry Seinfeld"}
        customers = [Customer.create(slug="tinsel", name="distracting")]
        response = {
            "verified_emails": frozenset(["jerry.seinfeld@bolor.com", "jerry.s.seinfeld@gmail.com", "jerry@gmail.com"]),
            "toolchain_customers": customers,
            "create_date": utcnow() - datetime.timedelta(days=10),
        }
        assert ToolchainUser.objects.count() == 0
        result = create_user(
            strategy=github_backend.strategy, details=details, backend=github_backend, user=None, response=response
        )
        assert ToolchainUser.objects.count() == 1
        new_user = ToolchainUser.objects.get(id=result["user"].id)
        assert result == {"is_new": True, "user": new_user}
        assert new_user.email == "jerry.seinfeld@bolor.com"
        assert new_user.username == "Seinfeld"
        assert new_user.full_name == "Jerry Seinfeld"
        assert new_user.avatar_url == ""
        assert new_user.is_active is True

    @pytest.mark.xfail(reason="disabled self service onboarding", strict=True, raises=AuthForbidden)
    def test_new_github_user_as_inactive(self, github_backend: ToolchainGithubOAuth2) -> None:
        details = {"email": "jerry@gmail.com", "username": "Seinfeld", "fullname": "Jerry Seinfeld"}
        response = {
            "verified_emails": frozenset(["jerry.seinfeld@bolor.com", "jerry.s.seinfeld@gmail.com", "jerry@gmail.com"]),
            "toolchain_customers": [],
            "create_date": utcnow() - datetime.timedelta(days=10),
        }
        assert ToolchainUser.objects.count() == 0
        result = create_user(
            strategy=github_backend.strategy, details=details, backend=github_backend, user=None, response=response
        )
        assert ToolchainUser.objects.count() == 1
        new_user = ToolchainUser.objects.get(id=result["user"].id)
        assert result == {"is_new": True, "user": new_user}
        assert new_user.email == "jerry.seinfeld@bolor.com"
        assert new_user.username == "Seinfeld"
        assert new_user.full_name == "Jerry Seinfeld"
        assert new_user.avatar_url == ""
        assert new_user.is_active is False

    def test_corp_email_with_edu_email(self, github_backend: ToolchainGithubOAuth2) -> None:
        details = {"email": "jerry@g.kyu.edu", "username": "Seinfeld", "fullname": "Jerry Seinfeld"}
        customers = [Customer.create(slug="tinsel", name="distracting")]
        response = {
            "verified_emails": frozenset(["jerry@zoomba.com", "jerry@kyu.edu", "jerry@protonmail.com"]),
            "toolchain_customers": customers,
        }
        assert ToolchainUser.objects.count() == 0
        result = create_user(
            strategy=github_backend.strategy, details=details, backend=github_backend, user=None, response=response
        )
        assert ToolchainUser.objects.count() == 1
        new_user = ToolchainUser.objects.get(id=result["user"].id)
        assert result == {"is_new": True, "user": new_user}
        assert new_user.email == "jerry@zoomba.com"
        assert new_user.username == "Seinfeld"
        assert new_user.full_name == "Jerry Seinfeld"
        assert new_user.avatar_url == ""
        assert new_user.is_active is True
