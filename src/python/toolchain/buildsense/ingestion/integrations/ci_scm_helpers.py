# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.bitbucket_integration.client.repo_clients import BitbucketRepoInfoClient
from toolchain.buildsense.ingestion.integrations.ci_integration import CIDFullDetails, get_ci_info
from toolchain.buildsense.records.run_info import CIDetails, RunInfo, RunType, ScmProvider
from toolchain.django.site.models import ToolchainUser
from toolchain.github_integration.client.repo_clients import GithubRepoInfoClient
from toolchain.users.client.user_client import UserClient

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScmUserInfo:
    username: str | None
    user_id: str


def update_ci_scm_data(scm: ScmProvider, run_info: RunInfo, ci_full_details: CIDFullDetails) -> bool:
    if scm == ScmProvider.GITHUB:
        return _update_ci_full_details_for_github_scm(run_info, ci_full_details=ci_full_details)
    if scm == ScmProvider.BITBUCKET:
        return _update_ci_full_details_for_bitbucket_scm(run_info, ci_full_details=ci_full_details)
    raise ToolchainAssertion(f"Invalid SCM: {scm=}")


def _update_ci_full_details_for_github_scm(run_info: RunInfo, ci_full_details: CIDFullDetails) -> bool:
    client = GithubRepoInfoClient.for_repo(settings, customer_id=run_info.customer_id, repo_id=run_info.repo_id)
    if ci_full_details.details.run_type == RunType.PULL_REQUEST:
        return _update_github_pr_info(client, run_info, ci_full_details)
    return _update_github_push_info(client, run_info, ci_full_details)


def _update_github_pr_info(client: GithubRepoInfoClient, run_info: RunInfo, ci_full_details: CIDFullDetails) -> bool:
    pr_number = ci_full_details.details.pull_request
    pr_info = client.get_pull_request_info(pr_number=pr_number)  # type: ignore[arg-type]
    if not pr_info:
        _logger.warning(f"No PR info on {pr_number=} repo={run_info.repo_id} run_id={run_info.run_id}")
        return False
    run_info.ci_info.link = pr_info.html_url  # type: ignore[union-attr]
    branch_changed = run_info.branch != pr_info.branch
    _logger.info(
        f"update_pr_info {pr_number=} repo={run_info.repo_id} run_id={run_info.run_id} old_branch={run_info.branch} new_branch={pr_info.branch} link={ci_full_details.details.link}"
    )
    run_info.branch = pr_info.branch
    run_info.title = pr_info.title
    return branch_changed


def _update_github_push_info(client: GithubRepoInfoClient, run_info: RunInfo, ci_full_details: CIDFullDetails) -> bool:
    commit_sha = run_info.revision or ci_full_details.sha1
    push_info = client.get_push_info(ref_name=ci_full_details.ref_name, commit_sha=commit_sha)  # type: ignore[arg-type]
    if not push_info:
        _logger.warning(
            f"No push info on branch={run_info.branch} commit={run_info.revision} repo={run_info.repo_id} run_id={run_info.run_id}"
        )
        return False
    run_info.ci_info.link = push_info.html_url  # type: ignore[union-attr]
    if push_info.message:
        run_info.title = push_info.message.splitlines()[0]
    return True


def _update_ci_full_details_for_bitbucket_scm(run_info: RunInfo, ci_full_details: CIDFullDetails) -> bool:
    client = BitbucketRepoInfoClient.for_repo(
        django_settings=settings, customer_id=run_info.customer_id, repo_id=run_info.repo_id
    )
    if ci_full_details.details.run_type == RunType.PULL_REQUEST:
        return _update_bitbucket_pr_info(client, run_info, ci_full_details)
    return _update_bitbucket_push_info(client, run_info, ci_full_details)


def _update_bitbucket_pr_info(
    client: BitbucketRepoInfoClient, run_info: RunInfo, ci_full_details: CIDFullDetails
) -> bool:
    pr_number = ci_full_details.details.pull_request
    pr_info = client.get_pull_request_info(pr_number=pr_number)  # type: ignore[arg-type]
    if not pr_info:
        _logger.warning(f"No PR info on {pr_number=} repo={run_info.repo_id} run_id={run_info.run_id}")
        return False
    run_info.ci_info.link = pr_info.html_url  # type: ignore[union-attr]
    branch_changed = run_info.branch != pr_info.branch
    _logger.info(
        f"update_pr_info {pr_number=} repo={run_info.repo_id} run_id={run_info.run_id} old_branch={run_info.branch} new_branch={pr_info.branch} link={ci_full_details.details.link}"
    )
    run_info.branch = pr_info.branch
    run_info.title = pr_info.title
    return branch_changed


def _update_bitbucket_push_info(
    client: BitbucketRepoInfoClient, run_info: RunInfo, ci_full_details: CIDFullDetails
) -> bool:
    push_info = client.get_push_info(ref_type=ci_full_details.details.run_type.value, ref_name=ci_full_details.ref_name, commit_sha=run_info.revision)  # type: ignore[arg-type]
    if not push_info:
        _logger.warning(
            f"No push info on branch={run_info.branch} commit={run_info.revision} repo={run_info.repo_id} run_id={run_info.run_id}"
        )
        return False
    run_info.ci_info.link = push_info.html_url  # type: ignore[union-attr]
    if push_info.message:
        run_info.title = push_info.message.splitlines()[0]
    return True


class ScmInfoHelper:
    def __init__(self, customer_id: str, repo_id: str, silence_timeouts: bool):
        self._customer_id = customer_id
        self._repo_id = repo_id
        self._silence_timeouts = silence_timeouts

    def get_ci_info(
        self, run_id: str, build_stats: dict, auth_user: ToolchainUser, ci_user: ToolchainUser | None
    ) -> tuple[CIDFullDetails | None, ToolchainUser | None]:
        run_info_json = build_stats["run_info"]
        ci_full_details = get_ci_info(build_stats.get("ci_env"), context=f"{run_id=}")
        if not ci_full_details:
            if ci_user:
                _logger.warning(f"CI User {ci_user} passed into non-ci build. this is unexpected and will be ignored.")
            return None, None

        run_info_json.setdefault("revision", ci_full_details.sha1)
        branch = run_info_json.get("branch")
        if not branch or branch == run_info_json["revision"] and ci_full_details.has_branch_name:
            # Under Travis CI, pants doesn't read the branch name correctly from git
            # It is really a travis issue. so we get the branch name from the travis env variables
            branch = ci_full_details.ref_name
            run_info_json["branch"] = branch
        if ci_user:
            return ci_full_details, ci_user
        ci_details = ci_full_details.details
        ci_username: str | None = ci_details.username

        ci_user = self.get_ci_user(current_user=auth_user, run_info_json=run_info_json, ci_full_details=ci_full_details)
        if ci_user:
            _logger.info(f"resolved_ci_user {ci_user=} from {ci_username=} {run_id=}")
        return ci_full_details, ci_user

    def get_ci_user(
        self, current_user: ToolchainUser, run_info_json: dict, ci_full_details: CIDFullDetails
    ) -> ToolchainUser | None:
        scm_user_info = self._get_user_info_from_scm(run_info_json, ci_full_details)
        if not scm_user_info:
            # username can be an empty string if user has never logged into CI.
            return None
        uc = UserClient.for_customer(django_settings=settings, customer_id=self._customer_id, current_user=current_user)
        scm_provider = UserClient.Auth(ci_full_details.scm.value)
        resolved_user_info = uc.resolve_ci_scm_user(scm_user_id=scm_user_info.user_id, scm=scm_provider)
        if not resolved_user_info:
            return None
        ci_full_details.details.username = resolved_user_info.scm_username
        return ToolchainUser.get_by_api_id(api_id=resolved_user_info.api_id)

    def _get_user_info_from_scm(self, run_info_json: dict, ci_full_details: CIDFullDetails) -> ScmUserInfo | None:
        ci_details = ci_full_details.details
        if ci_details.run_type == CIDetails.Type.PULL_REQUEST:
            return self.get_user_info_from_pr(scm=ci_full_details.scm, pr_number=ci_details.pull_request)  # type: ignore[arg-type]
        # Branch or Tag
        ref_name = ci_full_details.ref_name
        commit_sha = run_info_json.get("revision") or ci_full_details.sha1
        if not commit_sha:
            _logger.warning(f"No commit info for {ci_details.run_type.value} {ref_name=} can't resolve user.")
            return None
        return self.get_user_info_from_push(
            scm=ci_full_details.scm, ref_name=ref_name, commit_sha=commit_sha, run_type=ci_details.run_type
        )

    def get_user_info_from_pr(self, scm: ScmProvider, pr_number: int) -> ScmUserInfo | None:
        if scm == ScmProvider.GITHUB:
            return self._get_github_pr_user_data(pr_number)
        if scm == ScmProvider.BITBUCKET:
            return self._get_bitbucket_pr_user_data(pr_number)
        raise ToolchainAssertion(f"Unknown scm provider: {scm}")

    def get_user_info_from_push(
        self, scm: ScmProvider, ref_name: str, commit_sha: str, run_type: RunType
    ) -> ScmUserInfo | None:
        if scm == ScmProvider.GITHUB:
            return self._get_github_push_user_data(ref_name, commit_sha, run_type)
        if scm == ScmProvider.BITBUCKET:
            return self._get_bitbucket_push_user_data(ref_name, commit_sha, run_type)
        raise ToolchainAssertion(f"Unknown scm provider: {scm}")

    def _get_github_repo_client(self) -> GithubRepoInfoClient:
        return GithubRepoInfoClient.for_repo(
            settings, customer_id=self._customer_id, repo_id=self._repo_id, silence_timeouts=self._silence_timeouts
        )

    def _get_github_push_user_data(self, ref_name: str, commit_sha: str, run_type: RunType) -> ScmUserInfo | None:
        repo_client = self._get_github_repo_client()
        push_info = repo_client.get_push_info(ref_name=ref_name, commit_sha=commit_sha)
        _logger.info(f"get_push_data scm=github {run_type.value} {ref_name=} {commit_sha=} {push_info=}")
        return ScmUserInfo(username=push_info.sender_username, user_id=push_info.sender_user_id) if push_info else None

    def _get_bitbucket_push_user_data(self, ref_name: str, commit_sha: str, run_type: RunType) -> ScmUserInfo | None:
        repo_client = BitbucketRepoInfoClient.for_repo(
            django_settings=settings, customer_id=self._customer_id, repo_id=self._repo_id
        )
        push_info = repo_client.get_push_info(ref_type=run_type.value, ref_name=ref_name, commit_sha=commit_sha)
        _logger.info(f"get_user_info_from_push scm=bitbucket {run_type.value} {ref_name=} {commit_sha=} {push_info=}")
        return ScmUserInfo(username=None, user_id=push_info.user_account_id) if push_info else None

    def _get_github_pr_user_data(self, pr_number: int) -> ScmUserInfo | None:
        repo_client = self._get_github_repo_client()
        pr_info = repo_client.get_pull_request_info(pr_number=pr_number)  # type: ignore[arg-type]
        _logger.info(f"get_user_info_from_pr scm=github pull_request={pr_number} {pr_info=}")
        return ScmUserInfo(username=pr_info.username, user_id=pr_info.user_id) if pr_info else None

    def _get_bitbucket_pr_user_data(self, pr_number: int) -> ScmUserInfo | None:
        repo_client = BitbucketRepoInfoClient.for_repo(
            django_settings=settings, customer_id=self._customer_id, repo_id=self._repo_id
        )
        pr_info = repo_client.get_pull_request_info(pr_number=pr_number)
        _logger.info(f"get_user_info_from_pr scm=bitbucket pull_request={pr_number} {pr_info=}")
        return ScmUserInfo(username=None, user_id=pr_info.user_account_id) if pr_info else None
