# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from enum import Enum, unique
from pathlib import PurePath

from django.conf import settings
from django.core.cache import cache
from prometheus_client import Histogram

from toolchain.aws.s3 import S3
from toolchain.base.contexttimer import Timer
from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.site.models import Repo
from toolchain.github_integration.constants import GithubActionsCheckRun
from toolchain.github_integration.models import GithubRepo

_logger = logging.getLogger(__name__)


@unique
class RepoStat(Enum):
    RepoInfo = "repo_info"
    Views = "repo_views"
    Clones = "repo_clones"
    ReferralPaths = "repo_referral_paths"
    ReferralSources = "repo_referral_sources"


CACHE_TIMEOUT_SEC = timedelta(minutes=30).total_seconds()

_S3_LATENCY_BUCKETS = (0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 1, 1.5, 3, 4, 5, 8) + (
    10,
    15,
    20,
    30,
    40,
    50,
    60,
    70,
    80,
    float("inf"),
)

S3_READ_LATENCY = Histogram(
    name="toolchain_repo_data_store_read_latency",
    documentation="Histogram of read latency from repo data store (s3).",
    labelnames=["event_type", "scm", "result"],
    buckets=_S3_LATENCY_BUCKETS,
)

S3_WRITE_LATENCY = Histogram(
    name="toolchain_repo_data_store_write_latency",
    documentation="Histogram of write latency to repo data store (s3).",
    labelnames=["event_type", "scm"],
    buckets=_S3_LATENCY_BUCKETS,
)


def _upload_json(event_type: str, key: str, json_data: dict, update_cache: bool = True, context: str = "") -> None:
    s3 = S3()
    data = json.dumps(json_data)
    if update_cache:
        cache.set(key=key, value=data, timeout=CACHE_TIMEOUT_SEC)
    with Timer() as timer:
        s3.upload_json_str(bucket=settings.SCM_INTEGRATION_BUCKET, key=key, json_str=data)
    S3_WRITE_LATENCY.labels(event_type=event_type, scm="github").observe(timer.elapsed)
    _logger.info(f"{event_type} {key=} {context} latency={timer.elapsed:.3f}s")


def _get_json(event_type: str, key: str) -> dict | None:
    s3 = S3()
    content = cache.get(key=key, default=None)
    if not content:
        with Timer() as timer:
            content = s3.get_content_or_none(bucket=settings.SCM_INTEGRATION_BUCKET, key=key)
        S3_READ_LATENCY.labels(
            event_type=event_type, scm="github", result="success" if content else "not_found"
        ).observe(timer.elapsed)
        if content:
            cache.set(key=key, value=content, timeout=CACHE_TIMEOUT_SEC)
        if timer.elapsed > 1:
            _logger.info(f"get_json {event_type} {key=} latency={timer.elapsed:.3f}s")
    return json.loads(content) if content else None


class GithubRepoDataStore:
    _BRANCH_REF_PREFIX = "refs/heads/"
    _TAGS_REF_PREFIX = "refs/tags/"
    _PADDED_NUMBER_FACTOR = 7

    @classmethod
    def for_github_repo_id(cls, github_repo_id: str) -> GithubRepoDataStore | None:
        github_repo = GithubRepo.get_by_github_repo_id(github_repo_id)
        if not github_repo:
            _logger.warning(f"Can't find GitRepo with {github_repo_id=}")
            return None
        repo = Repo.get_by_slug_and_customer_id(customer_id=github_repo.customer_id, slug=github_repo.name)
        if not repo:
            _logger.warning(f"Can't Repo with customer_id={github_repo.customer_id} slug={github_repo.name}")
            return None
        return cls.for_repo(repo)

    @classmethod
    def check_access(cls) -> dict:
        key = (PurePath(settings.GITHUB_WEBHOOKS_STORE_KEY_PREFIX) / "testfile.json").as_posix()
        data = {"test-time": utcnow().isoformat()}
        _upload_json("check_access", key, data)
        loaded_data = _get_json("check", key)
        if not loaded_data:
            raise ToolchainAssertion(f"Failed to load test data from: {key}")
        return {"data": loaded_data, "key": key, "bucket": settings.SCM_INTEGRATION_BUCKET}

    @classmethod
    def for_repo(cls, repo: Repo) -> GithubRepoDataStore:
        return cls(customer_id=repo.customer_id, repo_id=repo.id)

    def __init__(self, customer_id: str, repo_id: str) -> None:
        self._customer_id = customer_id
        self._repo_id = repo_id

    def _get_key_path(self, event_type: str) -> PurePath:
        return PurePath(settings.GITHUB_WEBHOOKS_STORE_KEY_PREFIX) / event_type / self._customer_id / self._repo_id

    @property
    def _pr_base_path(self) -> PurePath:
        return self._get_key_path("pull_request")

    def _get_pr_paths(self, pr_number: str) -> tuple[str, str]:
        # For now, until migration is done, we need to support both
        padded_pr = pr_number.rjust(self._PADDED_NUMBER_FACTOR, "0")
        return (self._pr_base_path / f"{padded_pr}.json").as_posix(), (
            self._pr_base_path / f"{pr_number}.json"
        ).as_posix()

    def _get_push_path(self, *, ref_name: str, commit_sha: str) -> str:
        return (self._get_key_path("push") / ref_name / f"{commit_sha}.json").as_posix()

    def _get_check_run_path(self, check_run_id: str) -> str:
        return (self._get_key_path("check_run") / f"{check_run_id}.json").as_posix()

    def save_push(self, push_data: dict) -> bool:
        git_ref = push_data["ref"]
        commit_sha = push_data["head_commit"]["id"]
        # https://docs.github.com/en/rest/reference/git#references
        branch_ref = git_ref.startswith(self._BRANCH_REF_PREFIX)
        tag_ref = git_ref.startswith(self._TAGS_REF_PREFIX)
        if not (branch_ref or tag_ref):
            _logger.warning(f"Not storing unknown ref: {git_ref}")
            return False
        # ref name can contain slashes, which will create more "nesting" in the s3 key.
        # Currently, I don't think this is a problem.
        offset = len(self._BRANCH_REF_PREFIX if branch_ref else self._TAGS_REF_PREFIX)
        ref_name = git_ref[offset:]
        key = self._get_push_path(ref_name=ref_name, commit_sha=commit_sha)
        repo_fn = push_data["repository"]["full_name"]
        _upload_json("save_push", key=key, json_data=push_data, context=f"repo={repo_fn}")
        return True

    def get_push_data(self, *, ref_name: str, commit_sha: str) -> dict | None:
        key = self._get_push_path(ref_name=ref_name, commit_sha=commit_sha)
        push_data = _get_json("push", key)
        if not push_data:
            _logger.warning(f"get_push_data no_data {key=} bucket={settings.SCM_INTEGRATION_BUCKET}")
            return None
        return push_data

    def save_pull_request_from_webhook(self, pr_data: dict) -> None:
        pr_number = str(pr_data["number"])
        key = self._get_pr_paths(pr_number)[0]
        repo_fn = pr_data["repository"]["full_name"]
        _upload_json("save_pull_request", key=key, json_data=pr_data, context=f"repo={repo_fn}")

    def save_pull_request_from_api(self, pr_data: dict) -> bool:
        pr_number = str(pr_data["number"])
        keys = self._get_pr_paths(pr_number)
        data = json.dumps(pr_data)
        s3 = S3()
        s3.upload_json_str(bucket=settings.SCM_INTEGRATION_BUCKET, key=keys[0], json_str=data)
        return True

    def save_issue_from_webhook(self, payload: dict) -> None:
        issue_number = str(payload["issue"]["number"])
        key = self._get_pr_paths(issue_number)[0]
        repo_fn = payload["repository"]["full_name"]
        _upload_json("save_issue", key=key, json_data=payload, context=f"repo={repo_fn}", update_cache=False)

    def save_check_run(self, check_run_payload: dict) -> None:
        check_run_id = str(check_run_payload["check_run"]["id"])
        key = self._get_check_run_path(check_run_id)
        repo_fn = check_run_payload["repository"]["full_name"]
        # We currently never actually read this data, so don't cache it in memory
        _upload_json(
            "save_check_run", key=key, json_data=check_run_payload, update_cache=False, context=f"repo={repo_fn}"
        )

    def get_pull_request_data(self, pr_number: str) -> dict | None:
        keys = self._get_pr_paths(pr_number)
        for key in keys:
            pr_data = _get_json("pull_request", key)
            if pr_data:
                break
        if not pr_data:
            _logger.warning(f"No PR found at {keys=} bucket={settings.SCM_INTEGRATION_BUCKET}")
            return None
        if key != keys[0]:  # if we didn't use the first key and needed to fallback to the non-padded key
            _logger.warning(f"used_non_padded_key for repo={self._repo_id} {pr_number=} {keys=}")
        # For now, we don't want to return all the info in the webhook (sender, organization. repository)
        # When we read the the PR/Issue from the github API, the PR/issue data is not nested.
        # so for pr_data from an API the "sender" object is not present.
        if "sender" in pr_data:
            if "pull_request" not in pr_data:
                _logger.info(f"get_pull_request_data missing {pr_number} - webhooks, issue")
                return None
            return pr_data["pull_request"]
        if "head" not in pr_data:
            # head object is only present in PR objects, not issues.
            _logger.info(f"get_pull_request_data missing {pr_number} - api, issue")
            return None
        return pr_data

    def get_check_run(self, check_run_id: str) -> GithubActionsCheckRun | None:
        key = self._get_check_run_path(check_run_id)
        check_run_payload = _get_json("check_run", key=key)
        if not check_run_payload:
            _logger.warning(f"No check_run found at {key=} bucket={settings.SCM_INTEGRATION_BUCKET}")
            return None
        # For now, we don't want to return all the info in the webhook (sender, organization. repository)
        return GithubActionsCheckRun.from_json_dict(check_run_payload)

    def save_repo_stats_data(self, statistic: RepoStat, stats_data: dict, timestamp: datetime) -> None:
        timestamp_str = timestamp.isoformat(timespec="minutes")
        key = f"{settings.GITHUB_STATS_STORE_KEY_PREFIX}/{self._customer_id}/{self._repo_id}/{timestamp_str}/{statistic.value}.json"
        _upload_json("save_repo_stats", key=key, json_data=stats_data, update_cache=False)

    def get_all_issue_numbers(self) -> list[int]:
        s3 = S3()
        # This is not super efficient, however due to the way AWS orders keys we need to do it.
        keys_iter = s3.keys_with_prefix(
            bucket=settings.SCM_INTEGRATION_BUCKET, key_prefix=self._pr_base_path.as_posix(), page_size=1_000
        )
        return sorted(int(PurePath(key).stem) for key in keys_iter)
