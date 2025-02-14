# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import base64
import datetime
import json
from dataclasses import asdict, dataclass
from typing import cast

from toolchain.base.datetime_tools import utcnow


@dataclass(frozen=True)
class AuthToken:
    access_token: str
    expires_at: datetime.datetime
    user: str | None = None
    repo: str | None = None
    repo_id: str | None = None
    customer_id: str | None = None

    @classmethod
    def no_token(cls) -> AuthToken:
        return cls(access_token="", expires_at=datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc))  # nosec

    @classmethod
    def from_json_dict(cls, json_dict: dict):
        return cls(
            access_token=json_dict["access_token"],
            expires_at=datetime.datetime.fromisoformat(json_dict["expires_at"]),
            user=json_dict.get("user"),
            repo=json_dict.get("repo"),
            repo_id=json_dict.get("repo_id"),
            customer_id=json_dict.get("customer_id"),
        )

    @classmethod
    def from_access_token_string(cls, token_str: str) -> AuthToken:
        claims = cls.get_claims(token_str)
        expires_at = datetime.datetime.fromtimestamp(claims["exp"], tz=datetime.timezone.utc)
        return cls(
            access_token=token_str, expires_at=expires_at, user=claims["toolchain_user"], repo=claims["toolchain_repo"]
        )

    @classmethod
    def get_claims(cls, token_str):
        claims_segment = token_str.split(".")[1].encode()
        return json.loads(base64url_decode(claims_segment))

    def get_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}

    def has_expired(self) -> bool:
        expiration_time = cast(datetime.datetime, self.expires_at) - datetime.timedelta(
            seconds=10
        )  # Give some room for clock deviation and processing time.
        return utcnow() > expiration_time

    @property
    def has_token(self) -> bool:
        return bool(self.access_token)

    @property
    def claims(self) -> dict:
        return self.get_claims(self.access_token)

    @property
    def token_id(self) -> str:
        return self.claims["jid"]

    def to_json_string(self) -> str:
        token_dict = asdict(self)
        token_dict["expires_at"] = self.expires_at.isoformat()
        return json.dumps(token_dict)


def base64url_decode(data: bytes) -> bytes:
    # based on jose/utils.py
    rem = len(data) % 4
    if rem > 0:
        data += b"=" * (4 - rem)
    return base64.urlsafe_b64decode(data)
