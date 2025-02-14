# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import hashlib
import logging
from dataclasses import dataclass

import httpx
from jose import jwt

from toolchain.base.datetime_tools import utcnow

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BitBucketRepo:
    repo_id: str
    name: str
    slug: str
    full_name: str
    is_private: bool

    @classmethod
    def from_response(cls, json_repo: dict) -> BitBucketRepo:
        return cls(
            repo_id=json_repo["uuid"],
            full_name=json_repo["full_name"],
            name=json_repo["name"],
            slug=json_repo["slug"],
            is_private=json_repo["is_private"],
        )


class BitBucketAppClient:
    _JWT_TTL = datetime.timedelta(minutes=5)

    def __init__(self, *, app_key: str, secret: str, client_key: str) -> None:
        self._app_key = app_key
        self._secret = secret
        self._client_key = client_key
        self._client = httpx.Client(base_url="https://api.bitbucket.org/")

    def _generate_jwt_auth(self, method: str, path: str) -> dict[str, str]:
        # https://developer.atlassian.com/cloud/bitbucket/understanding-jwt-for-apps/#creating-a-jwt-token
        # https://bitbucket.org/atlassian/bitbucket-connect/src/master/src/http-client.js
        now = utcnow()
        qsh_data = f"{method.upper()}&/{path}&".encode()
        payload = {
            "iat": now,
            "exp": now + self._JWT_TTL,
            "iss": self._app_key,
            "sub": self._client_key,
            "qsh": hashlib.sha256(qsh_data).hexdigest(),
        }
        jwt_token = jwt.encode(claims=payload, key=self._secret, algorithm="HS256")
        return {
            "Authorization": f"JWT {jwt_token}",
        }

    def list_repos(self, workspace: str) -> tuple[BitBucketRepo, ...]:
        path = f"2.0/repositories/{workspace}"
        headers = self._generate_jwt_auth("GET", path)
        response = self._client.get(path, headers=headers)
        # TODO: Better error handling
        response.raise_for_status()
        # TODO: support pagination
        json_response = response.json()
        return tuple(BitBucketRepo.from_response(repo) for repo in json_response["values"])
