# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
import logging
from dataclasses import dataclass

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.auth.claims import Claims, load_claims
from toolchain.django.auth.impersonation import ImpersonationData
from toolchain.django.site.models import ToolchainUser

_logger = logging.getLogger(__name__)
INTERNAL_AUTH_HEADER = "X-Toolchain-Internal-Auth"
INTERNAL_CALL_HEADER = "X-Toolchain-Internal-Call"


@dataclass
class HeaderAuthData:
    user: ToolchainUser
    claims: Claims | None
    impersonation: ImpersonationData | None = None


def is_internal_call(headers: dict) -> bool:
    return bool(headers.get(INTERNAL_CALL_HEADER))


def get_auth_data(headers: dict, path: str) -> HeaderAuthData | None:
    internal_auth_data = headers.get(INTERNAL_AUTH_HEADER)
    if not internal_auth_data:
        # This log message is noisy since passing the auth header is not fully implemented in service router.
        # _logger.warning(f"{INTERNAL_AUTH_HEADER} header missing for {path}.")
        return None
    # This is a json dict since in the future we are going to put more data there so we
    # can avoid accessing the models (user, customer, repo) in internal services
    # for now we only pass the user api ID and load it here.
    auth_json_data = json.loads(internal_auth_data)
    user_api_id = auth_json_data["user"]["api_id"]
    # It is expected that the XXXX upstream will only put valid user api id into this header
    # there is a chance for race conditions (when a user is being deactivated, which we currently don't support)
    # so eventually we need to handle that use case.
    user = ToolchainUser.get_by_api_id(user_api_id)
    claims = load_claims(auth_json_data["claims"]) if "claims" in auth_json_data else None
    auth_data = HeaderAuthData(user=user, claims=claims)
    if "impersonation" in auth_json_data:
        impersonation_json = auth_json_data["impersonation"]
        if user_api_id != user.api_id:
            raise ToolchainAssertion(f"Unexpected user impersonation data {impersonation_json}.")
        impersonator = ToolchainUser.get_by_api_id(impersonation_json["impersonator_api_id"])
        if not impersonator:
            raise ToolchainAssertion(f"Failed to load impersonator: {impersonation_json}.")

        auth_data.impersonation = ImpersonationData(
            user=user,
            impersonator=impersonator,
            expiry=datetime.datetime.fromisoformat(impersonation_json["expiry"]),
        )
    return auth_data


def create_internal_auth_headers(
    user: ToolchainUser, claims: dict | None, impersonation: ImpersonationData | None
) -> dict[str, str]:
    # Eventually we want to put more data here (and possibly sign it using a secret key to avoid spoofing)
    # putting more data into this header means that internal services don't have to access the users db and load
    # User/Customer/Repo data themselves.
    internal_auth_data = {"user": {"api_id": user.api_id}}
    if claims:
        internal_auth_data["claims"] = claims
    if impersonation:
        internal_auth_data["impersonation"] = impersonation.to_json_dict()

    return {
        "Remote-User": f"{user.username}/{user.api_id}",  # this is just for logging purposes (nginx will log this header).
        INTERNAL_AUTH_HEADER: json.dumps(internal_auth_data),
        INTERNAL_CALL_HEADER: "1",
    }
