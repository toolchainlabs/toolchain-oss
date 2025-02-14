# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from collections.abc import Iterator

from django.core.management.base import BaseCommand

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.site.models import Repo
from toolchain.github_integration.app_client import GithubRepoClient, get_repo_client
from toolchain.github_integration.models import GithubRepo
from toolchain.github_integration.repo_data_store import GithubRepoDataStore

_logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Add a worker that fetches stats from a GitHub repo at a given interval"

    def handle(self, *args, **options) -> None:
        customer_slug, _, repo_slug = options["repo"].partition("/")
        repo = Repo.get_for_slugs_or_none(customer_slug=customer_slug, repo_slug=repo_slug)
        if not repo:
            raise ToolchainAssertion(f"Invalid customer/repo slugs: {customer_slug}/{repo_slug}")
        github_repo = GithubRepo.get_or_none(customer_id=repo.customer_id, name=repo_slug)
        backfill_issues(repo=repo, github_repo=github_repo)

    def add_arguments(self, parser):
        parser.add_argument("--repo", required=True, help="GitHub Repo in format `github-org/repo-name`")


def backfill_issues(repo: Repo, github_repo: GithubRepo) -> None:
    repo_store = GithubRepoDataStore.for_repo(repo)
    all_issue_numbers = repo_store.get_all_issue_numbers()
    pages = get_missing_issue_pages(existing_issues=all_issue_numbers, page_size=GithubRepoClient.ISSUES_PAGE_SIZE)
    _logger.info(f"get issues for pages: {pages}")
    gh_client = get_repo_client(github_repo)
    for page in pages:
        issues = gh_client.list_issues(page=page)
        for issue in issues:
            repo_store.save_pull_request_from_api(issue)


def get_missing_issue_pages(existing_issues: list[int], page_size: int) -> tuple[int, ...]:
    pages = []
    latest_issue = 0
    latest_page = 0
    for from_issue, to_issue in find_gaps_iter(existing_issues):
        from_issue_page = int((from_issue - 1) / page_size) + 1
        if from_issue_page < latest_page:
            continue
        if latest_page >= from_issue_page:
            from_issue_page = latest_page + 1
        pages.append(from_issue_page)
        latest_issue = from_issue_page * page_size
        latest_page = from_issue_page
        while latest_issue < to_issue:
            latest_page = int((latest_issue + 1) / page_size) + 1
            pages.append(latest_page)
            latest_issue += page_size
    return tuple(pages)


def find_gaps_iter(existing_issues: list[int]) -> Iterator[tuple[int, int]]:
    missing_issues = sorted(set(range(1, existing_issues[-1])).difference(existing_issues))
    index = 0
    cnt = len(missing_issues)
    while index < cnt - 1:
        offset = 0
        low = missing_issues[index]
        while cnt > (index + offset) and (missing_issues[index + offset] - low) <= offset:
            offset += 1
        yield low, missing_issues[index + offset - 1]
        index += offset
