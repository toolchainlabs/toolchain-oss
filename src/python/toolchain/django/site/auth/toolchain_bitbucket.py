# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

from social_core.backends.bitbucket import BitbucketOAuth2
from social_django.models import DjangoStorage
from social_django.strategy import DjangoStrategy

_logger = logging.getLogger(__name__)


class ToolchainBitbucketOAuth2(BitbucketOAuth2):
    name = "bitbucket"
    # account_id seems to be the preferred way since it identifies the user across atlassian products/services
    # while uuid (the default in BitbucketOAuth2) seems to be bitbucket specific.
    # See: https://developer.atlassian.com/cloud/bitbucket/bitbucket-api-changes-gdpr/#changes-to-querying
    ID_KEY = "account_id"

    @classmethod
    def get_strategy(cls, request=None) -> DjangoStrategy:
        return DjangoStrategy(DjangoStorage, request)

    @classmethod
    def for_request(cls, request, redirect_uri: str) -> ToolchainBitbucketOAuth2:
        backend = cls(cls.get_strategy(request), redirect_uri)
        request.social_strategy = backend.strategy
        request.backend = backend
        return backend

    def __init__(self, strategy=None, redirect_uri: str | None = None) -> None:
        super().__init__(strategy or self.get_strategy(), redirect_uri=redirect_uri)

    @property
    def full_backend_name(self) -> str:
        cls = type(self)
        return f"{cls.__module__}.{cls.__name__}"

    def user_data(self, access_token, *args, **kwargs):
        # The implementation in BitbucketOAuthBase.user_data is to generic. overriding it here to match our needs.
        emails_response = self._get_emails(access_token)
        user = self._get_user(access_token)
        verified_emails = [addr["email"] for addr in emails_response["values"] if addr["is_confirmed"] is True]
        primary_emails = [
            addr["email"] for addr in emails_response["values"] if addr["is_confirmed"] is True and addr["is_primary"]
        ]
        organization_names = self._get_workspaces(access_token)
        user.update(organization_names=frozenset(organization_names), verified_emails=frozenset(verified_emails))
        if primary_emails:
            user["email"] = primary_emails[0]
        _logger.info(
            f"auth_user_data bitbucket username={user['username']} user_id={user[self.ID_KEY]} emails={verified_emails} orgs={organization_names}"
        )
        return user

    def _get_workspaces(self, access_token: str) -> tuple[str, ...]:
        # https://developer.atlassian.com/bitbucket/api/2/reference/resource/workspaces
        response = self._do_bitbucket_request(access_token=access_token, path="workspaces")
        if response.get("next"):
            _logger.warning("More than one page in bitbucket workspace endpoint")
        values = response["values"]
        if not values:
            _logger.warning(f"No workspaces membership found for user. {response}")
            return tuple()
        workspaces_slugs = tuple(ws["slug"] for ws in values if ws["type"] == "workspace")
        if len(workspaces_slugs) != len(values):
            _logger.warning(f"Unknown value types in workspaces responses: {values}")
        return workspaces_slugs

    def _get_user(self, access_token: str) -> dict:  # pylint: disable=signature-differs
        # https://developer.atlassian.com/bitbucket/api/2/reference/resource/user
        return self._do_bitbucket_request(access_token=access_token, path="user")

    def _get_emails(self, access_token: str) -> dict:  # pylint: disable=signature-differs
        # https://developer.atlassian.com/bitbucket/api/2/reference/resource/user/emails
        return self._do_bitbucket_request(access_token=access_token, path="user/emails")

    def _do_bitbucket_request(self, access_token: str, path: str) -> dict:
        # Base implementation is sending access tokens via query params, which is not desirable.
        # see: https://developer.atlassian.com/bitbucket/api/2/reference/meta/authentication
        headers = {"Authorization": f"Bearer {access_token}"}
        return self.get_json(f"https://api.bitbucket.org/2.0/{path}", headers=headers)
