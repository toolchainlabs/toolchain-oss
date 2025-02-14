# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from pathlib import PurePath

from django.conf import settings
from django.core.management.base import BaseCommand

from toolchain.aws.s3 import S3
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.site.models import Repo
from toolchain.github_integration.repo_data_store import GithubRepoDataStore

_logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Migrates issues and PRs stored in s3 to the new padded format."

    def handle(self, *args, **options) -> None:
        dry_run = not options["no_dry_run"]
        repo_fn = options["repo"]
        if repo_fn:
            customer_slug, _, repo_slug = repo_fn.partition("/")
            repo = Repo.get_for_slugs_or_none(customer_slug=customer_slug, repo_slug=repo_slug)
            if not repo:
                raise ToolchainAssertion(f"Invalid customer/repo slugs: {customer_slug}/{repo_slug}")
            migrate_repo(repo, dry_run)
        elif options["all"] is True:
            migrate_all_repos(dry_run)
        else:
            _logger.warning("Must specify a repo or --all for all repos.")

    def add_arguments(self, parser):
        parser.add_argument("--repo", required=False, default=None, help="GitHub Repo in format `github-org/repo-name`")
        parser.add_argument(
            "--all", action="store_true", required=False, default=False, help="migrate all repos for all customers"
        )
        parser.add_argument("--no-dry-run", action="store_true", required=False, default=False, help="Dry run.")


def migrate_all_repos(dry_run: bool) -> None:
    for repo in Repo.objects.all():
        migrate_repo(repo, dry_run)


def migrate_repo(repo: Repo, dry_run: bool) -> None:
    repo_fn = f"{repo.customer.slug}/{repo.slug}"
    migrated_keys_count = 0
    bucket = settings.SCM_INTEGRATION_BUCKET
    pr_base_path = GithubRepoDataStore.for_repo(repo)._pr_base_path.as_posix()
    s3 = S3()
    for key in s3.keys_with_prefix(bucket=bucket, key_prefix=pr_base_path):
        key_path = PurePath(key)
        is_padded, new_padded_pr_num = check_padding(key_path)
        if is_padded:
            continue
        new_key = (PurePath(key).parent / f"{new_padded_pr_num}.json").as_posix()
        _logger.info(f"Copy {key} to {new_key} for {repo_fn} {dry_run=}")
        if not dry_run:
            s3.copy_object(old_bucket=bucket, old_key=key, new_bucket=bucket, new_key=new_key)
        migrated_keys_count += 1
    if migrated_keys_count:
        _logger.info(f"Migrated {migrated_keys_count} for {repo_fn}")
    else:
        _logger.info(f"No keys migrated for {repo_fn}")


def check_padding(key_path: PurePath) -> tuple[bool, str]:
    pr_number = str(int(key_path.stem))  # Get rid of the leading zeros if there are any
    new_padded_pr_num = pr_number.rjust(GithubRepoDataStore._PADDED_NUMBER_FACTOR, "0")
    return new_padded_pr_num == key_path.stem, new_padded_pr_num
