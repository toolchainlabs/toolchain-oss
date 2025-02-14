# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
import re

from toolchain.django.site.models import Repo
from toolchain.github_integration.api.constants import CIChecksResults
from toolchain.github_integration.api.exceptions import CIResolveError
from toolchain.github_integration.app_client import GithubServerError, get_repo_client
from toolchain.github_integration.constants import GithubActionsWorkflowRun
from toolchain.github_integration.models import GithubRepo

_logger = logging.getLogger(__name__)


_EXPECTED_VARS = ("GITHUB_RUN_ID", "GITHUB_REF", "GITHUB_EVENT_NAME", "GITHUB_SHA")
_PR_REF_EXPRESSION = re.compile(r"^refs/pull/(?P<pr_num>\d+)/merge$")


def _check_vars(ci_env_vars: dict[str, str]):
    missing = sorted(name for name in _EXPECTED_VARS if not ci_env_vars.get(name))
    if missing:
        raise CIResolveError("github_actions", f"Missing environment variables: {missing}")


def check_github_actions_build(
    repo: Repo, ci_env_vars: dict[str, str], start_threshold: datetime.timedelta
) -> CIChecksResults:
    _check_vars(ci_env_vars)
    run_id = ci_env_vars["GITHUB_RUN_ID"]
    event_name = ci_env_vars["GITHUB_EVENT_NAME"]
    github_sha = ci_env_vars["GITHUB_SHA"]
    if event_name != "pull_request":
        raise CIResolveError("github_actions", f"Invalid {event_name=} {run_id=} {repo=}")
    github_repo = GithubRepo.get_for_customer_and_slug(customer_id=repo.customer_id, repo_slug=repo.slug)
    if not github_repo:
        raise CIResolveError("github_actions", f"No active github repo for {repo=}")
    try:
        repo_client = get_repo_client(github_repo)
        workflow_run, _ = repo_client.get_workflow_actions_run(run_id)
    except GithubServerError:
        raise CIResolveError("github_actions", "github_server_error")
    if not workflow_run:
        raise CIResolveError("github_actions", f"Unknown {run_id=} {repo=}")
    pr_number = _check_valid_run(
        workflow_run,
        run_id=run_id,
        github_ref=ci_env_vars["GITHUB_REF"],
    )
    # TODO: GITHUB_SHA doesn't seem to match head_sha from check_run/pr webhooks. will need to figure out why.
    _logger.info(f"check_github_actions_build {run_id=} {github_sha=} head_sha={workflow_run.head_sha}")
    # TODO: fix uniqueness issue that is created due to run_id being reused when the user re-runs the job.
    key = f"gha_{workflow_run.check_suite_id}_{workflow_run.run_id}"  # gha for github-actions
    _logger.info(f"check_github_actions_build {key=} {workflow_run.possibly_unique_values}")
    return CIChecksResults(
        ci_type="github_actions", build_key=key, pull_request_number=pr_number, job_link=workflow_run.url
    )


def _check_valid_run(workflow_run: GithubActionsWorkflowRun, run_id: str, github_ref: str) -> str:
    if run_id != workflow_run.run_id:
        raise CIResolveError("github_actions", f"run_id mismatch {run_id=} workflow_run_id={workflow_run.run_id}")
    if not workflow_run.is_pull_request:
        raise CIResolveError("github_actions", f"Invalid event type event={workflow_run.event} {run_id=}")
    if not workflow_run.is_running_or_queued:
        # The github API can report an action queued while it is actually running, so account for that.
        raise CIResolveError("github_actions", f"Invalid build status={workflow_run.status} {run_id=}")

    pr_match = _PR_REF_EXPRESSION.match(github_ref)
    if not pr_match:
        raise CIResolveError("github_actions", f"Can't parse PR number {github_ref=} {run_id=}")
    return pr_match.group("pr_num")
