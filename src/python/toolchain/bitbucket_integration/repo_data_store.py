# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import logging
from pathlib import PurePath

from django.conf import settings

from toolchain.aws.s3 import S3
from toolchain.django.site.models import Repo

_logger = logging.getLogger(__name__)


def _upload_json(key: str, json_data: dict) -> None:
    s3 = S3()
    s3.upload_json_str(bucket=settings.SCM_INTEGRATION_BUCKET, key=key, json_str=json.dumps(json_data))


def _get_json(key: str) -> dict | None:
    s3 = S3()
    content = s3.get_content_or_none(bucket=settings.SCM_INTEGRATION_BUCKET, key=key)
    return json.loads(content) if content else None


class BitbucketRepoDataStore:
    @classmethod
    def for_repo(cls, repo: Repo) -> BitbucketRepoDataStore:
        return cls(customer_id=repo.customer_id, repo_id=repo.id)

    def __init__(self, customer_id: str, repo_id: str) -> None:
        self._customer_id = customer_id
        self._repo_id = repo_id

    def _get_key_path(self, event_type: str) -> PurePath:
        return PurePath(settings.BITBUCKET_STORE_KEY_PREFIX) / event_type / self._customer_id / self._repo_id

    def _get_pr_path(self, pr_number: str) -> str:
        return (self._get_key_path("pull_request") / f"{pr_number}.json").as_posix()

    def save_pull_request(self, payload: dict) -> None:
        payload_data = payload["data"]
        pr_number = payload_data["pullrequest"]["id"]
        key = self._get_pr_path(str(pr_number))
        repo_fn = payload_data["repository"]["full_name"]
        _logger.info(f"save_pull_request repo={repo_fn} {key=}")
        _upload_json(key=key, json_data=payload)

    def get_pull_request_data(self, pr_number: str) -> dict | None:
        key = self._get_pr_path(pr_number)
        json_data = _get_json(key)
        if not json_data:
            _logger.warning(f"No PR found at {key=} bucket={settings.SCM_INTEGRATION_BUCKET}")
            return None
        # For now, we don't want to return all the info in the webhook.
        return json_data["data"]["pullrequest"]

    def _get_push_path(self, *, push_type: str, ref_name: str, commit_sha: str) -> str:
        return (self._get_key_path("push") / push_type / ref_name / f"{commit_sha}.json").as_posix()

    def save_push(self, payload: dict) -> bool:
        payload_data = payload["data"]
        repo_fn = payload_data["repository"]["full_name"]
        change_data = payload_data["push"]["changes"][0]["new"]
        if change_data is None:
            _logger.info(f"save_push branch_deleted repo={repo_fn}")
            return False
        commit_sha = change_data["target"]["hash"]
        push_type = change_data["type"]
        ref_name = change_data["name"]
        key = self._get_push_path(push_type=push_type, ref_name=ref_name, commit_sha=commit_sha)
        _logger.info(f"save_push {push_type=} repo={repo_fn} {key=}")
        _upload_json(key=key, json_data=payload)
        return True

    def get_push_data(self, *, push_type: str, ref_name: str, commit_sha: str) -> dict | None:
        key = self._get_push_path(push_type=push_type, ref_name=ref_name, commit_sha=commit_sha)
        json_data = _get_json(key)
        if not json_data:
            _logger.warning(f"No push data found at {key=} bucket={settings.SCM_INTEGRATION_BUCKET}")
            return None
        return json_data["data"]
