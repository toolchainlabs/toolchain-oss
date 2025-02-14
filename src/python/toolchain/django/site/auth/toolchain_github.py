# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from urllib.parse import urljoin

from dateutil.parser import parse
from requests import HTTPError, RequestException
from social_core.backends.github import GithubOAuth2
from social_core.exceptions import AuthFailed
from social_core.utils import SSLHttpAdapter
from social_django.models import DjangoStorage
from social_django.strategy import DjangoStrategy

from toolchain.base.contexttimer import Timer

_logger = logging.getLogger(__name__)


class ToolchainGithubOAuth2(GithubOAuth2):
    @classmethod
    def get_strategy(cls, request=None):
        return DjangoStrategy(DjangoStorage, request)

    @classmethod
    def for_request(cls, request, redirect_uri):
        backend = cls(cls.get_strategy(request), redirect_uri)
        request.social_strategy = backend.strategy
        request.backend = backend
        return backend

    def __init__(self, strategy=None, redirect_uri=None):
        super().__init__(strategy or self.get_strategy(), redirect_uri=redirect_uri)

    @property
    def full_backend_name(self) -> str:
        cls = type(self)
        return f"{cls.__module__}.{cls.__name__}"

    def user_data(self, access_token, *args, **kwargs):
        """Loads user data from service."""
        data = self._user_data(access_token)
        primary_email_addr = data.get("email")
        user_handle = data["login"]
        created_at = data.get("created_at")
        github_account_creation_date = parse(created_at) if created_at else None
        if not github_account_creation_date:
            # Soft check for now, make it a hard check later on.
            _logger.warning(f"missing Github account creation date: {created_at=} {data}")
        try:
            emails = self._user_data(access_token, "/emails")
            user_data_orgs_names, user_orgs_names = self._get_all_orgs(user_handle, access_token)
        except (HTTPError, ValueError, TypeError) as err:
            _logger.warning(f"Github API call failed: {err!r}", exc_info=True)
            emails = []
            user_data_orgs_names = user_orgs_names = []
        _logger.info(f"Got orgs response for `{user_handle}` {user_data_orgs_names=} {user_orgs_names=}")
        if not emails:
            return data
        verified_emails = [email["email"] for email in emails if email["verified"] is True]
        org_names = frozenset(user_data_orgs_names + user_orgs_names)

        data.update(
            emails=verified_emails,
            verified_emails=frozenset(verified_emails),
            organization_names=org_names,
            create_date=github_account_creation_date,
        )
        if primary_email_addr:
            email = primary_email_addr
        else:
            primary_emails = [
                email["email"] for email in emails or email["primary"] is True and email["verified"] is True
            ]
            if primary_emails:
                email = primary_emails[0]
            else:
                _logger.warning(f"Could not find email for user: user_data={data} email_data={emails}")
                email = None
        data["email"] = email
        _logger.info(
            f"auth_user_data github username={user_handle} user_id={data[self.ID_KEY]} emails={verified_emails} orgs={tuple(org_names)}"
        )
        return data

    def _get_all_orgs(self, username, access_token: str) -> tuple[list[str], list[str]]:
        orgs = self._user_data(access_token, "/orgs")  # only returns orgs where the GH app is installed
        user_data_orgs_names = [org["login"] for org in orgs]
        url = urljoin(self.api_url(), f"users/{username}/orgs")
        orgs = self.get_json(
            url, headers={"Authorization": f"token {access_token}"}
        )  # returns orgs where membership is public
        user_orgs_names = [org["login"] for org in orgs]
        return user_data_orgs_names, user_orgs_names

    def _user_data(self, access_token: str, path: str | None = None):
        # Temporary override for the method in the base class until https://github.com/python-social-auth/social-core/pull/428 makes it upstream.
        path = path or ""
        url = urljoin(self.api_url(), f"user{path}")
        headers = {"Authorization": f"token {access_token}"}
        return self.get_json(url, headers=headers)

    def request(self, url: str, method: str = "GET", **kwargs):
        kwargs.setdefault("headers", {})
        kwargs["headers"]["User-Agent"] = "Toolchain.com integration"
        kwargs.setdefault("timeout", 3)
        session = SSLHttpAdapter.ssl_adapter_session(self.SSL_PROTOCOL)
        with Timer() as timer:
            try:
                response = session.request(method, url, **kwargs)
            except ConnectionError as err:
                raise AuthFailed(self, str(err))
        extra = "" if response.ok else f" {response.text[:350]}"
        _logger.info(
            f"github_login_api_request {url=} status={response.status_code} elapsed={timer.elapsed:.3f}sec{extra}"
        )
        response.raise_for_status()
        return response

    def get_org_admins(self, access_token: str, org_slug: str) -> list[dict]:
        # https://docs.github.com/en/rest/reference/orgs#list-organization-members
        headers = {"Authorization": f"token {access_token}"}
        url = urljoin(self.api_url(), f"orgs/{org_slug}/members?role=admin&per_page=100")
        # Very low timeout value since this happens during login and we don't want this to create issues
        # when GH is having issues. Also we have logic to handle errors and ignore them.
        return self.get_json(url, headers=headers, timeout=1)

    def is_org_admin(self, org_slug: str, github_user_id: str, access_token: str) -> bool | None:
        try:
            org_admins = self.get_org_admins(access_token=access_token, org_slug=org_slug)
        except RequestException as err:
            _logger.warning(f"Failed to get org admins for {org_slug} - {err!r}")
            return None
        return any(str(admin["id"]) == github_user_id for admin in org_admins)
