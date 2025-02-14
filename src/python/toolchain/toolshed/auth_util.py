# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging

from toolchain.django.site.models import ToolchainUser
from toolchain.toolshed.site import ToolshedAdminSite
from toolchain.users.models import AuthProvider, UserAuth

_logger = logging.getLogger(__name__)


class FakeSocial:
    # this object here is to comply with the social-core reqs
    # Specifically, this is meant to look like a subclass of social_core.storage.UserMixin
    provider = "github"


def check_toolchain_access(backend, details, response, request, *args, **kwargs):
    user_handle = details["username"]
    github_user_id = response["id"]
    user_auth = UserAuth.get_by_user_id(provider=AuthProvider.GITHUB, user_id=github_user_id)
    if not user_auth:
        return _access_denied(request, user_handle, github_user_id)
    user = ToolchainUser.get_by_api_id(user_auth.user_api_id)
    if not user or not user.is_staff:
        # TODO: check that user is part of the toolchain customer org.
        # TODO: this should be generating alerts since access to this login page is behind a VPN.
        return _access_denied(request, user_handle, github_user_id)
    return {"user": user, "social": FakeSocial}


def _access_denied(request, user_handle: str, github_user_id: str):
    _logger.warning(f"Access denied for github_user={user_handle} {github_user_id=}")
    return ToolshedAdminSite.login_error(request, "Access deined.")
