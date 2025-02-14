# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.config.endpoints import get_gunicorn_service_endpoint
from toolchain.django.auth.utils import INTERNAL_CALL_HEADER, create_internal_auth_headers
from toolchain.django.site.middleware.request_context import get_current_request_id
from toolchain.django.site.models import ToolchainUser
from toolchain.users.common.constants import AuthProvider
from toolchain.util.constants import REQUEST_ID_HEADER

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolvedCIUser:
    username: str
    api_id: str
    scm: AuthProvider
    scm_username: str

    @classmethod
    def from_response(cls, json_data: dict) -> ResolvedCIUser:
        # Allow flexibility for backward compatibility
        scm_username = json_data.get("scm_username") or json_data["github_username"]
        scm_name = json_data.get("scm", AuthProvider.GITHUB.value)
        return cls(
            username=json_data["username"],
            api_id=json_data["api_id"],
            scm=AuthProvider(scm_name),
            scm_username=scm_username,
        )


@dataclass(frozen=True)
class AdminUser:
    username: str
    email: str


class UserClient:
    Auth = AuthProvider

    @classmethod
    def for_customer(
        cls, django_settings, *, customer_id: str, current_user: ToolchainUser | None = None
    ) -> UserClient:
        service_endpoint = get_gunicorn_service_endpoint(django_settings, "users/api")
        service_name = django_settings.SERVICE_INFO.name
        return cls(
            service_name=service_name, base_url=service_endpoint, customer_id=customer_id, current_user=current_user
        )

    def __init__(
        self, *, service_name: str, base_url: str, customer_id: str, current_user: ToolchainUser | None
    ) -> None:
        headers = {"User-Agent": f"Toolchain-Internal/{service_name}", INTERNAL_CALL_HEADER: "1"}
        req_id = get_current_request_id()
        if req_id:
            headers[REQUEST_ID_HEADER] = req_id
        if current_user:
            headers.update(create_internal_auth_headers(current_user, claims=None, impersonation=None))
        self._client = httpx.Client(
            base_url=urljoin(base_url, f"/internal/api/v1/customers/{customer_id}/"),
            timeout=3,
            headers=headers,
            transport=httpx.HTTPTransport(retries=3),
        )

    def resolve_ci_scm_user(self, *, scm_user_id: str, scm: AuthProvider) -> ResolvedCIUser | None:
        if not scm_user_id:
            raise ToolchainAssertion(f"Invalid {scm_user_id=}")
        with self._client as session:
            # See users/urls_api.py
            response = session.get("users/resolve/", params={"user_id": scm_user_id, "scm": scm.value})
        if response.status_code in {403, 404}:
            # 403 and 404 are a legit response for this API
            _logger.warning(f"resolve_ci_scm_user_fail status={response.status_code} {scm_user_id=}")
            return None
        # TODO: more error handling
        response.raise_for_status()
        ci_user_json = response.json()["user"]
        return ResolvedCIUser.from_response(ci_user_json)

    def get_admin_users(self) -> tuple[AdminUser, ...]:
        with self._client as session:
            # See users/urls_api.py
            response = session.get("users/admin/")
        response.raise_for_status()
        return tuple(AdminUser(**admin) for admin in response.json()["admins"])
