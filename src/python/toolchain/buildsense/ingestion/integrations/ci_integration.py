# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import quote

from toolchain.base.toolchain_error import ToolchainError
from toolchain.buildsense.records.run_info import CIDetails, CISystem, RunType, ScmProvider

_logger = logging.getLogger(__name__)


class InvalidCIData(ToolchainError):
    """Raised when a CI parser can't find expexted fields and thus unable to resolve/parse CI infi."""


@dataclass
class CIDFullDetails:
    details: CIDetails
    scm: ScmProvider
    ref_name: str
    sha1: str | None

    @property
    def has_branch_name(self) -> bool:
        return self.details.run_type in {RunType.BRANCH, RunType.PULL_REQUEST}

    @property
    def ci_system(self) -> CISystem:
        return self.details.ci_system


class CircleCI:
    _BUILD_URLS_MATCH = "https://circleci.com/"

    @classmethod
    def get_ci_info(cls, ci_env: dict[str, str]) -> CIDFullDetails | None:
        # https://circleci.com/docs/2.0/env-vars/#built-in-environment-variables
        if not ci_env.get("CIRCLECI"):
            return None
        pr_num_str = ci_env.get("CIRCLE_PR_NUMBER")
        if pr_num_str:
            run_type = RunType.PULL_REQUEST
            pr_num: int | None = int(pr_num_str)
            username = ci_env["CIRCLE_PR_USERNAME"]
        else:
            run_type = RunType.BRANCH
            pr_num = None
            username = ci_env["CIRCLE_USERNAME"]
        build_url = ci_env["CIRCLE_BUILD_URL"]
        ref_name = ci_env["CIRCLE_BRANCH"]
        details = CIDetails(
            run_type=run_type,
            pull_request=pr_num,
            username=username,
            job_name=ci_env["CIRCLE_JOB"],
            build_num=int(ci_env["CIRCLE_BUILD_NUM"]),
            build_url=build_url if build_url.startswith(cls._BUILD_URLS_MATCH) else None,
            ref_name=ref_name,
        )
        return CIDFullDetails(
            details=details,
            scm=ScmProvider.GITHUB,  # CircleCI can work w/ Bitbucket, so we need to support that at some point
            sha1=ci_env["CIRCLE_SHA1"],
            ref_name=ref_name,
        )


class TravisCI:
    _BUILD_URLS_MATCH = "https://travis-ci.com/"

    @classmethod
    def get_ci_info(cls, ci_env: dict[str, str]) -> CIDFullDetails | None:
        # https://docs.travis-ci.com/user/environment-variables/#default-environment-variables
        if ci_env.get("TRAVIS", "") != "true":
            return None
        pr_num_str = ci_env.get("TRAVIS_PULL_REQUEST", "false")

        if pr_num_str != "false":
            run_type = RunType.PULL_REQUEST
            pr_num: int | None = int(pr_num_str)  # type: ignore[arg-type]
            owner, _, repo = ci_env["TRAVIS_REPO_SLUG"].partition("/")
            username, *_ = ci_env["TRAVIS_PULL_REQUEST_SLUG"].partition("/")
            if username == owner:
                username = ""
            branch = ci_env["TRAVIS_PULL_REQUEST_BRANCH"]
        else:
            run_type = RunType.BRANCH
            pr_num = None
            username = ""
            branch = ci_env["TRAVIS_BRANCH"]
        build_url = ci_env.get("TRAVIS_BUILD_WEB_URL") or ""
        details = CIDetails(
            run_type=run_type,
            pull_request=pr_num,
            username=username,
            job_name=ci_env.get("TRAVIS_JOB_NAME"),
            build_num=int(ci_env["TRAVIS_BUILD_NUMBER"]),
            build_url=build_url if build_url.startswith(cls._BUILD_URLS_MATCH) else None,
            ref_name=branch,
        )
        return CIDFullDetails(
            scm=ScmProvider.GITHUB, details=details, sha1=ci_env.get("TRAVIS_COMMIT"), ref_name=branch
        )


class GithubActionsCI:
    _PR_REF_EXPRESSION = re.compile(r"^refs/pull/(?P<pr_num>\d+)/merge$")
    _BRANCH_REF_EXPRESSION = re.compile(r"^refs/heads/(?P<branch>\S+)$")
    _TAG_REF_EXPRESSION = re.compile(r"^refs/tags/(?P<tag_name>\S+)$")

    @classmethod
    def get_ci_info(cls, ci_env: dict[str, str]) -> CIDFullDetails | None:
        # https://docs.github.com/en/actions/reference/environment-variables
        if ci_env.get("GITHUB_ACTIONS", "") != "true":
            return None
        github_ref = ci_env["GITHUB_REF"]
        event = ci_env["GITHUB_EVENT_NAME"]
        if event == "pull_request":
            run_type = RunType.PULL_REQUEST
            pr_match = cls._PR_REF_EXPRESSION.match(github_ref)
            if not pr_match:
                raise InvalidCIData(f"Github Actions PR: can't parse github_ref: {github_ref}")
            pr_num: int | None = int(pr_match.group("pr_num"))  # type: ignore[arg-type,union-attr]
            ref_name = ci_env["GITHUB_HEAD_REF"]
        else:
            pr_num = None
            branch_match = cls._BRANCH_REF_EXPRESSION.match(github_ref)
            if branch_match:
                run_type = RunType.BRANCH
                ref_name = branch_match.group("branch")
            else:
                run_type = RunType.TAG
                ref_name = cls._TAG_REF_EXPRESSION.match(github_ref).group("tag_name")  # type: ignore[arg-type,union-attr]

        build_url = (
            f"{ci_env['GITHUB_SERVER_URL']}/{ci_env['GITHUB_REPOSITORY']}/actions/runs/{ci_env['GITHUB_RUN_ID']}"
        )
        workflow_name = ci_env.get("GITHUB_WORKFLOW")
        gha_job_name = ci_env.get("GITHUB_JOB")
        if workflow_name and gha_job_name:
            job_name = f"{workflow_name} [{gha_job_name}]"
        else:
            job_name = workflow_name or gha_job_name or "N/A"
        details = CIDetails(
            run_type=run_type,
            pull_request=pr_num,
            username=ci_env["GITHUB_ACTOR"],
            job_name=job_name,
            build_num=int(ci_env["GITHUB_RUN_NUMBER"]),
            build_url=build_url,
            ref_name=ref_name,
        )
        return CIDFullDetails(details=details, scm=ScmProvider.GITHUB, sha1=ci_env.get("GITHUB_SHA"), ref_name=ref_name)


class BitBucketPipelines:
    @classmethod
    def get_ci_info(cls, ci_env: dict[str, str]) -> CIDFullDetails | None:
        # https://support.atlassian.com/bitbucket-cloud/docs/variables-and-secrets/
        if not ci_env.get("BITBUCKET_COMMIT", ""):
            return None
        repo_full_name = ci_env["BITBUCKET_REPO_FULL_NAME"]
        build_num = ci_env["BITBUCKET_BUILD_NUMBER"]
        step_uuid = ci_env["BITBUCKET_STEP_UUID"]
        pr_num: int | None = None
        if "BITBUCKET_TAG" in ci_env:
            ref_name = ci_env["BITBUCKET_TAG"]
            run_type = RunType.TAG
        else:
            ref_name = ci_env["BITBUCKET_BRANCH"]
            if "BITBUCKET_PR_ID" in ci_env:
                run_type = RunType.PULL_REQUEST
                pr_num = int(ci_env["BITBUCKET_PR_ID"])
            else:
                run_type = RunType.BRANCH
        build_url = f"https://bitbucket.org/{repo_full_name}/addon/pipelines/home#!/results/{build_num}/steps/{quote(step_uuid)}"
        details = CIDetails(
            run_type=run_type,
            pull_request=pr_num,
            build_num=int(build_num),
            build_url=build_url,
            username="",  # Bitbucket doesn't provide that, so we will get it via API
            job_name="Bitbucket pipeline job",  # This is not exposed via API or env variables.
            ref_name=ref_name,
        )
        return CIDFullDetails(
            details=details, scm=ScmProvider.BITBUCKET, sha1=ci_env["BITBUCKET_COMMIT"], ref_name=ref_name
        )


class Buildkite:
    _BUILD_URLS_MATCH = "https://buildkite.com/"

    @classmethod
    def get_ci_info(cls, ci_env: dict[str, str]) -> CIDFullDetails | None:
        # https://buildkite.com/docs/pipelines/environment-variables#bk-env-vars
        if ci_env.get("BUILDKITE", "") != "true":
            return None

        scm = ScmProvider(ci_env["BUILDKITE_PROJECT_PROVIDER"])
        branch_name = ci_env["BUILDKITE_BRANCH"]
        pr_num: int | None = None
        if ci_env["BUILDKITE_PULL_REQUEST"] == "false":
            run_type = RunType.BRANCH  # TODO: git tags
        else:
            run_type = RunType.PULL_REQUEST
            pr_num = int(ci_env["BUILDKITE_PULL_REQUEST"])
        ref_name = branch_name
        build_url = f"{ci_env['BUILDKITE_BUILD_URL']}#{ci_env['BUILDKITE_JOB_ID']}"
        details = CIDetails(
            run_type=run_type,
            pull_request=pr_num,
            username="",  # Buildkite doesn't provide that, so we will get it via the SCM provider API
            job_name=ci_env["BUILDKITE_LABEL"],
            build_num=int(ci_env["BUILDKITE_BUILD_NUMBER"]),
            ref_name=ref_name,
            build_url=build_url if build_url.startswith(cls._BUILD_URLS_MATCH) else None,
        )
        return CIDFullDetails(details=details, scm=scm, sha1=ci_env["BUILDKITE_COMMIT"], ref_name=ref_name)


_CI_CLASSES = (GithubActionsCI, CircleCI, BitBucketPipelines, Buildkite, TravisCI)


def get_ci_info(ci_env: dict[str, str] | None, context: str) -> CIDFullDetails | None:
    if not ci_env:
        return None
    ci_details = None
    for ci in _CI_CLASSES:
        try:
            ci_details = ci.get_ci_info(ci_env)  # type: ignore[attr-defined]
        except InvalidCIData as error:
            _logger.warning(f"Can't parse CI Data: {error} for {context}")
        if ci_details:
            return ci_details
    return None
