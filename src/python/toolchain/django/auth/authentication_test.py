# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from unittest.mock import MagicMock

import pytest

from toolchain.django.auth.authentication import InternalViewAuthentication
from toolchain.django.site.models import ToolchainUser
from toolchain.django.site.test_helpers.models_helpers import create_github_user


@pytest.mark.django_db()
class TestInternalServicesMiddleware:
    @pytest.fixture()
    def auth(self) -> InternalViewAuthentication:
        return InternalViewAuthentication()

    @pytest.fixture()
    def user(self) -> ToolchainUser:
        return create_github_user(
            username="kramer", email="kramer@jerrysplace.com", full_name="Cosmo Kramer", github_user_id="8837733"
        )

    def test_auth(self, auth: InternalViewAuthentication, user: ToolchainUser) -> None:
        req = MagicMock(internal_service_call_user=user)
        auth_tuple = auth.authenticate(req)
        assert auth_tuple == (user, None)

    def test_no_auth(self, auth: InternalViewAuthentication) -> None:
        req = MagicMock(internal_service_call_user=None)
        assert auth.authenticate(req) is None
