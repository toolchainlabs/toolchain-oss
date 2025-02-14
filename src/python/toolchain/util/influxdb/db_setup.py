# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass

from influxdb_client import Authorization, InfluxDBClient, Permission, PermissionResource

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.util.influxdb.client import get_client_for_admin, get_org

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InfluxDBUser:
    username: str
    token: str
    password: str | None = None

    @classmethod
    def from_dict(cls, json_dict: dict) -> InfluxDBUser:
        return cls(**json_dict)

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def add_access_user(
    admin: InfluxDBUser, service: str, username: str, override: bool
) -> tuple[InfluxDBUser | None, str]:
    """Creates a user with r/w permissions.

    If the user already exists (by username) returns None. Also returns org id.
    """
    perms = [
        Permission(action="read", resource=PermissionResource(type="orgs")),
        Permission(action="read", resource=PermissionResource(type="buckets")),
        Permission(action="write", resource=PermissionResource(type="buckets")),
    ]
    return _add_user(admin, service, username, perms, override)


def add_readonly_user(admin: InfluxDBUser, service: str, username: str, override: bool) -> InfluxDBUser | None:
    """Creates a user with read only permissions, if the user already exists (by username) returns None."""
    perms = [
        Permission(action="read", resource=PermissionResource(type="orgs")),
        Permission(action="read", resource=PermissionResource(type="buckets")),
    ]
    return _add_user(admin, service, username, perms, override)[0]


def _get_user_id_or_none(client: InfluxDBClient, username: str) -> str | None:
    users_response = client.users_api()._service.get_users()
    return next((user.id for user in users_response.users if user.name == username), None)


def _add_user(
    admin: InfluxDBUser,
    service: str,
    username: str,
    permissions: list[Permission],
    override: bool,
) -> tuple[InfluxDBUser | None, str]:
    client = get_client_for_admin(admin.token)
    org = get_org(client, service)
    if not org:
        raise ToolchainAssertion(f"Can't find org: {service}")
    user_id = _get_user_id_or_none(client, username)
    if user_id and not override:
        return None, org.id

    user_id = user_id or client.users_api().create_user(username).id
    auth = client.authorizations_api().create_authorization(
        authorization=Authorization(org_id=org.id, permissions=permissions, user_id=user_id)
    )
    _logger.info(f"create user {username=} for org={org.name}")
    return InfluxDBUser(username=username, token=auth.token), org.id


def add_org(admin: InfluxDBUser, org_name: str) -> str:
    client = get_client_for_admin(admin.token)
    org = get_org(client, org_name)
    if not org:
        _logger.info(f"create InfluxDB org: {org_name}")
        org = client.organizations_api().create_organization(name=org_name)
    return org.id
