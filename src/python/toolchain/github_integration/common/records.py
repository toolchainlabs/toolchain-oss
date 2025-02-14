# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from toolchain.base.toolchain_error import ToolchainError


class InvalidGithubEvent(ToolchainError):
    """Raised when the github event data can't be parsed."""


@dataclass(frozen=True)
class GitHubEvent:
    event_type: str
    event_id: str
    new_signature: str
    payload: bytes
    json_payload: dict

    @classmethod
    def from_json(cls, json_data: dict) -> GitHubEvent:
        return cls(
            event_type=json_data["event_type"],
            event_id=json_data["event_id"],
            new_signature=json_data["new_signature"],
            payload=b"",
            json_payload=json_data["json_payload"],
        )

    @property
    def signature(self) -> str:
        return self.new_signature

    @classmethod
    def create(cls, headers: dict[str, str], body: bytes) -> GitHubEvent:
        """See: https://developer.github.com/webhooks/#delivery-headers"""
        try:
            return cls(
                event_type=headers["X-GitHub-Event"],
                event_id=headers["X-GitHub-Delivery"],
                new_signature=headers["X-Hub-Signature-256"],
                payload=body,
                json_payload=json.loads(body),
            )
        except KeyError as error:
            raise InvalidGithubEvent(f"Failed to load data from {headers=}: {error!r}")

    def to_json_dict(self) -> dict:
        json_dict = asdict(self)
        del json_dict["payload"]
        json_dict["signature"] = self.signature
        return json_dict


@dataclass(frozen=True)
class PullRequestInfo:
    number: int
    branch: str
    username: str
    user_id: str
    html_url: str
    title: str
    state: str
    head_sha: str

    @classmethod
    def from_pr_data(cls, pr_data: dict) -> PullRequestInfo:
        user = pr_data["user"]
        return cls(
            number=pr_data["number"],
            branch=pr_data["head"]["ref"],
            username=user["login"],
            user_id=str(user["id"]),
            html_url=pr_data["html_url"],
            title=pr_data["title"],
            state=pr_data["state"],
            head_sha=pr_data["head"]["sha"],
        )

    @property
    def is_open(self) -> bool:
        return self.state == "open"
