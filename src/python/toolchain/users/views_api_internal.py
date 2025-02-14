# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from enum import Enum, unique

from django.http import Http404, HttpResponseBadRequest
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.auth.authentication import InternalViewAuthentication
from toolchain.django.site.models import Customer, ToolchainUser
from toolchain.users.models import AuthProvider, UserAuth, UserCustomerAccessConfig

_logger = logging.getLogger(__name__)
USE_REQUEST_USER_ARG = "me"


class BaseUserApiInternalView(APIView):
    view_type = "app"
    authentication_classes = (InternalViewAuthentication,)
    permission_classes = (IsAuthenticated,)


@unique
class ErrorType(Enum):
    NOT_FOUND = "not_found"
    DENIED = "denied"


class ResolveUserView(BaseUserApiInternalView):
    # A view to resolve ToolChainUser from a GH/CI username or user ID and check for impersonation permissions

    def get(self, request, customer_pk: str) -> Response:
        # Not required yet, will make it a required param after clients install
        scm_user_id = request.query_params.get("user_id")
        scm_username = request.query_params.get("username")
        if not scm_user_id and not scm_username:
            _logger.warning(f"Must provider username or user_id: {request.query_params}")
            return Response(status=HttpResponseBadRequest.status_code, data={"detail": "Missing params."})
        scm_provider_name = request.query_params.get("scm")
        if scm_provider_name:
            scm_provider = AuthProvider(scm_provider_name)
        elif scm_user_id:
            _logger.warning(f"Must provider scm: {request.query_params}")
            return Response(status=HttpResponseBadRequest.status_code, data={"detail": "scm param missing."})
        else:
            # Backward compatibility, scm provider is optional while we transition to lookup by user ids.
            scm_provider = AuthProvider.GITHUB
        if scm_username or not scm_provider_name:
            _logger.warning(f"resolve_user_view legacy_mode {request.query_params}")
        current_user = request.internal_service_call_user
        error_type, ci_user, resolved_scm_username = get_user_for_ci_username_or_user_id(
            current_user=current_user,
            customer_id=customer_pk,
            username=scm_username,
            user_id=scm_user_id,
            provider=scm_provider,
        )
        if not ci_user:
            if error_type == ErrorType.NOT_FOUND:
                raise Http404
            # if error_type == ErrorType.DENIED
            return self.permission_denied(request, message="Impersonate permission denied.")

        return Response(
            data={
                "user": {
                    "username": ci_user.username,
                    "api_id": ci_user.api_id,
                    "scm_username": resolved_scm_username,
                    "scm": scm_provider.value,
                    # Keeping this around for backward compatibility
                    "github_username": resolved_scm_username,
                }
            }
        )


class AdminUsersView(APIView):
    view_type = "app"
    authentication_classes = tuple()  # type: ignore [var-annotated]
    permission_classes = tuple()  # type: ignore [var-annotated]

    def get(self, request, customer_pk: str) -> Response:
        customer = Customer.get_or_404(id=customer_pk)
        admin_users_api_ids = UserCustomerAccessConfig.get_customer_admins(customer)
        if not admin_users_api_ids:
            return Response(data={"admins": []})
        admins = ToolchainUser.with_api_ids(user_api_ids=admin_users_api_ids)
        data = {"admins": [_serialize_user(admin) for admin in admins if admin.email]}
        return Response(data=data)


def _serialize_user(user: ToolchainUser) -> dict:
    return {"username": user.username, "email": user.email}


def get_user_for_ci_username_or_user_id(
    *,
    current_user: ToolchainUser,
    customer_id: str,
    username: str | None,
    user_id: str | None,
    provider: AuthProvider,
) -> tuple[ErrorType | None, ToolchainUser | None, str | None]:
    if username:
        user_auth = UserAuth.get_by_username(provider=provider, username=username)
    elif user_id:
        user_auth = UserAuth.get_by_user_id(provider=provider, user_id=user_id)
    else:
        raise ToolchainAssertion("Must provider username or user_id")
    if not user_auth:
        _logger.warning(f"Can't resolve username={username} for customer_id={customer_id}")
        return ErrorType.NOT_FOUND, None, None

    ci_user = ToolchainUser.get_by_api_id(api_id=user_auth.user_api_id, customer_id=customer_id, include_inactive=True)
    if not ci_user:
        _logger.warning(f"Can't find toolchain user for {user_auth} customer_id={customer_id}")
        return ErrorType.NOT_FOUND, None, None
    if ci_user.api_id == current_user.api_id:
        return None, ci_user, user_auth.username
    allowed_audiences = UserCustomerAccessConfig.get_audiences_for_user(
        customer_id=customer_id, user_api_id=current_user.api_id
    )
    if not allowed_audiences.can_impersonate:
        _logger.warning(
            f"missing_impersonation_permissions {current_user.username}/{current_user.api_id} {customer_id=} {allowed_audiences=}"
        )
        return ErrorType.DENIED, None, None
    can_impersonate = current_user.is_same_customer_associated(
        other_user_api_id=ci_user.api_id, customer_id=customer_id
    )
    if not can_impersonate:
        _logger.warning(f"User {current_user} cannot impersonate {ci_user} for {customer_id=}")
        return ErrorType.DENIED, None, None
    return None, ci_user, user_auth.username
