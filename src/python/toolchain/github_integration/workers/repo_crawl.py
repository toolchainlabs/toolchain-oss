# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import httpx

from toolchain.aws.errors import is_transient_aws_error
from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.site.models import Repo
from toolchain.github_integration.app_client import get_repo_client
from toolchain.github_integration.models import GithubRepo, GithubRepoStatsConfiguration
from toolchain.github_integration.repo_data_store import GithubRepoDataStore, RepoStat
from toolchain.workflow.constants import WorkExceptionCategory
from toolchain.workflow.worker import Worker

logger = logging.getLogger(__name__)


class GithubRepoStats(Worker):
    work_unit_payload_cls = GithubRepoStatsConfiguration

    def do_work(self, work_unit_payload: GithubRepoStatsConfiguration) -> bool:
        github_repo = GithubRepo.get_by_github_repo_id(work_unit_payload.repo_id)
        if not github_repo:
            logger.warning(f"GithubRepoStats: no repo found for repo_id {work_unit_payload.repo_id}")
            return True
        repo = Repo.get_by_slug_and_customer_id(customer_id=github_repo.customer_id, slug=github_repo.name)
        if not repo:
            raise ToolchainAssertion(f"Can't load Repo for github repo: {github_repo}")
        gh_client = get_repo_client(github_repo, timeout=30)

        cur_time = utcnow()

        repo_stats_data = [
            (RepoStat.RepoInfo, gh_client.get_repo_info()),
            (RepoStat.Views, gh_client.get_repo_views()),
            (RepoStat.Clones, gh_client.get_clones()),
            (RepoStat.ReferralPaths, gh_client.get_popular_referral_paths()),
            (RepoStat.ReferralSources, gh_client.get_popular_referral_sources()),
        ]

        repo_store = GithubRepoDataStore(customer_id=repo.customer_id, repo_id=repo.id)

        for name, stats_values in repo_stats_data:
            repo_store.save_repo_stats_data(name, stats_values, cur_time)

        # If period_minutes is None, this is a one-off job, don't repeat it. Otherwise
        # it should repeat every `period_minute` minutes.
        return work_unit_payload.period_minutes is None

    def on_reschedule(self, work_unit_payload: GithubRepoStatsConfiguration) -> datetime:
        """Reschedule based on the period_minutes field contiained in GithubRepoStatsConfiguration objects."""
        reschedule_at = utcnow() + timedelta(minutes=work_unit_payload.period_minutes)
        return reschedule_at

    def classify_error(self, exception: Exception) -> WorkExceptionCategory | None:
        if is_transient_aws_error(exception):
            return WorkExceptionCategory.TRANSIENT
        if isinstance(exception, (httpx.HTTPError, httpx.TransportError)):
            return WorkExceptionCategory.TRANSIENT
        return None

    def transient_error_retry_delay(
        self, work_unit_payload: GithubRepoStatsConfiguration, exception: Exception
    ) -> timedelta:
        return timedelta(minutes=10)
