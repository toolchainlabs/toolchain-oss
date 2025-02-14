# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import asdict, dataclass

from toolchain.base.toolchain_error import ToolchainError

_logger = logging.getLogger(__name__)


class InvaliBitBucketEvent(ToolchainError):
    """Raised when the bitbucket event data can't be parsed."""


def read_jwt(headers: Mapping[str, str]) -> str:
    if "Authorization" not in headers:
        raise InvaliBitBucketEvent(f"jwt_missing: {headers=}")
    jwt_header = headers["Authorization"]
    name, _, jwt_str = jwt_header.partition(" ")
    if name != "JWT":
        raise InvaliBitBucketEvent(f"Unexpected name in Authorization header: {jwt_header=}")
    return jwt_str


def _get_link(data: dict, link_name: str) -> str:
    return data["links"][link_name]["href"]


@dataclass(frozen=True)
class WebhookEvent:
    event_type: str
    event_id: str
    hook_id: str
    jwt: str | None
    attempt_number: int
    payload: bytes
    json_payload: dict

    @classmethod
    def create(cls, *, headers: Mapping[str, str], body: bytes) -> WebhookEvent:
        """https://support.atlassian.com/bitbucket-cloud/docs/event-payloads/#EventPayloads-Created.1."""
        try:
            return cls(
                event_type=headers["X-Event-Key"],
                event_id=headers["X-Request-Uuid"],
                hook_id=headers["X-Hook-Uuid"],
                attempt_number=int(headers["X-Attempt-Number"]),
                jwt=read_jwt(headers),
                payload=body,
                json_payload=json.loads(body),
            )
        except (KeyError, ValueError) as error:
            raise InvaliBitBucketEvent(f"Failed to load data from {headers=}: {error!r}")

    @classmethod
    def from_json_dict(cls, json_data) -> WebhookEvent:
        return cls(payload=b"", **json_data)

    def to_json_dict(self) -> dict:
        json_dict = asdict(self)
        del json_dict["payload"]
        return json_dict


@dataclass(frozen=True)
class AppInstallEvent:
    account_type: str
    account_url: str
    account_name: str
    account_id: str
    client_key: str
    shared_secret: str
    jwt: str

    @classmethod
    def from_payload(cls, jwt: str, json_payload: dict) -> AppInstallEvent:
        principle = json_payload["principal"]
        account_type = principle["type"]
        if account_type == "team":
            account_name = principle["username"]
            shared_secret = json_payload["sharedSecret"]
        elif account_type == "user":
            account_name = ""
            # shared secret doesn't seem to be in the payload when installing into personal accounts.
            # but we don't really care about this scenario currently, so we just need to make it work/pass in order to
            # allow the app review to pass
            shared_secret = json_payload.get("sharedSecret", "")
        else:
            account_name = ""
            shared_secret = ""
            _logger.error(f"AppInstallEvent: Unknown bitbucket account type: {account_type=} {json_payload}")
        return cls(
            account_name=account_name,
            account_type=account_type,
            account_url=_get_link(principle, "self"),
            account_id=principle["uuid"],
            client_key=json_payload["clientKey"],
            shared_secret=shared_secret,
            jwt=jwt,
        )

    @classmethod
    def from_json(cls, json_data: dict) -> AppInstallEvent:
        return cls(
            account_name=json_data["account_name"],
            account_id=json_data["account_id"],
            client_key=json_data["client_key"],
            shared_secret=json_data["shared_secret"],
            jwt=json_data["jwt"],
            account_type=json_data["account_type"],
            account_url=json_data["account_url"],
        )

    def to_json_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class AppUninstallEvent:
    account_type: str
    account_url: str
    account_name: str
    account_id: str
    client_key: str
    jwt: str

    @classmethod
    def from_payload(cls, jwt: str, json_payload: dict) -> AppUninstallEvent:
        principle = json_payload["principal"]
        account_type = principle["type"]
        if account_type == "team":
            account_name = principle["username"]
        elif account_type == "user":
            account_name = ""
        else:
            _logger.error(f"AppUninstallEvent: Unknown bitbucket account type: {account_type=} {json_payload}")
        return cls(
            account_name=account_name,
            account_type=account_type,
            account_url=_get_link(principle, "self"),
            account_id=principle["uuid"],
            client_key=json_payload["clientKey"],
            jwt=jwt,
        )

    @classmethod
    def from_json(cls, json_data: dict) -> AppUninstallEvent:
        return cls(
            account_name=json_data["account_name"],
            account_id=json_data["account_id"],
            client_key=json_data["client_key"],
            jwt=json_data["jwt"],
            account_type=json_data["account_type"],
            account_url=json_data["account_url"],
        )

    def to_json_dict(self) -> dict[str, str]:
        return asdict(self)
