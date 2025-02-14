# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging

from rest_framework.permissions import BasePermission

from toolchain.django.auth.claims import Claims, RepoClaims

_logger = logging.getLogger(__name__)


class AccessTokensPermissions(BasePermission):
    def has_permission(self, request, view) -> bool:
        user = request.user
        claims: Claims = request.auth
        if not claims:
            return False
        audience = view.audience
        has_audience = claims.has_audience(audience)
        if not has_audience:
            _logger.warning(f"audience mismatch: view.audience={view.audience} token_audience={claims.audience}")
            return False
        if not isinstance(claims, RepoClaims):
            return True
        repo_claims: RepoClaims = claims
        user_api_id = repo_claims.impersonated_user_api_id
        if not user_api_id:
            return True
        if not repo_claims.can_impersonate:
            _logger.warning(f"Impersonation specified ({user_api_id}) without proper permission.")
            return False
        if not user.is_same_customer_associated(user_api_id, repo_claims.customer_pk):
            _logger.warning(f"user {user} tried to impersonate {user_api_id} and was denied.")
            return False
        return True
