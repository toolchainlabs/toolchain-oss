# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
import re
from collections.abc import Iterator
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from git import BadName, GitCommandError, Repo
from git.objects import Commit

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion, ToolchainError


class InvalidCommitSha(ToolchainError):
    pass


logger = logging.getLogger(__name__)

_UPSTREAM_REPO_PARTIAL_URL = "toolchainlabs/toolchain"


@dataclass(frozen=True)
class CommitInfo:
    message: str
    timestamp: datetime.datetime
    author_name: str
    changed_files: tuple[str, ...]

    @classmethod
    def from_commit(cls, commit: Commit) -> CommitInfo:
        message = commit.summary if isinstance(commit.summary, str) else commit.summary.decode()
        return cls(
            message=message.strip(),
            timestamp=commit.authored_datetime,
            author_name=(commit.author.name if commit.author else "") or "",
            changed_files=tuple(sorted(str(fn) for fn in commit.stats.files.keys())),
        )

    def __str__(self):
        return f"{self.message} ({self.author_name})"


def _get_head_commit():
    return Repo(".").head.commit


def get_commit_sha() -> str:
    return _get_head_commit().hexsha


def get_commits_with_files(from_sha: str, to_sha: str, files_filter: tuple[str, ...]) -> Iterator[CommitInfo]:
    expressions = tuple(re.compile(exp) for exp in files_filter)
    repo = Repo(".")
    try:
        for commit in repo.iter_commits(rev=f"{from_sha}..{to_sha}"):
            for changed_file in commit.stats.files.keys():
                cf = str(changed_file)
                for exp in expressions:
                    if exp.match(cf):
                        yield CommitInfo.from_commit(commit)
                        break
    except GitCommandError as error:
        if "invalid revision range" in error.stderr.lower():
            raise InvalidCommitSha(error.stderr)
        raise


def iter_changed_files(from_sha: str, to_sha: str) -> Iterator[str]:
    repo = Repo(".")
    diffs = repo.commit(from_sha).diff(repo.commit(to_sha))
    for diff in diffs:
        yield diff.b_path


def get_version_tag() -> str:
    commit = _get_head_commit()
    dt_str = commit.committed_datetime.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d.%H-%M-%S")
    return f"{dt_str}-{commit.hexsha[:12]}"


def get_last_commit_timestamp() -> datetime.datetime:
    commit = _get_head_commit()
    return commit.committed_datetime.astimezone(datetime.timezone.utc)


def get_changed_paths(ref1: str, ref2: str, repo_root: str | Path = ".") -> list[str] | None:
    """Return the paths of files that are different between the two refs.

    Returns None if either ref is invalid.
    """

    def get_commit(ref):
        if not ref:
            logger.info(f'Invalid ref "{ref}"')
            return None
        with suppress(BadName):
            return repo.commit(ref)

    repo = Repo(repo_root)
    c1 = get_commit(ref1)
    c2 = get_commit(ref2)
    if c1 is None or c2 is None:
        return None

    diff_index = c1.diff(c2)
    changed_paths: set[str] = set()
    for change_type in diff_index.change_type:
        for diff in diff_index.iter_change_type(change_type):
            changed_paths.add(diff.a_path)
            changed_paths.add(diff.b_path)
    return sorted(changed_paths)


def matched_paths_changed(regex_pattern: str, ref1: str, ref2: str, repo_root: str | Path = ".") -> bool:
    """False iff the two refs are valid, and we know that no paths matching the pattern changed between them.

    If either ref is invalid, we assume the worst, namely that some matching path did change.
    """
    matcher = re.compile(regex_pattern)
    changed_paths = get_changed_paths(ref1, ref2, repo_root)
    if changed_paths is None:
        return True
    for path in changed_paths:
        if matcher.match(path):
            logger.info(f"{path} changed.")
            return True
    return False


def _get_upstream_master(repo: Repo, fetch: bool = True) -> Commit:
    upstream_remote = None
    for remote in repo.remotes:
        for url in remote.urls:
            if _UPSTREAM_REPO_PARTIAL_URL in url:
                upstream_remote = remote
                break
    if not upstream_remote:
        raise ToolchainAssertion(
            f"Couldn't find upstream remote (no remote mounted with URL containing: {_UPSTREAM_REPO_PARTIAL_URL}"
        )
    if fetch:
        upstream_remote.fetch()
    return next(ref for ref in upstream_remote.refs if ref.name == f"{upstream_remote.name}/master").commit


def _get_parent_commits(commit: Commit, max_count: int, min_date: datetime.datetime) -> list[Commit]:
    commits: list[Commit] = []
    while len(commits) < max_count:
        commits.append(commit)
        if len(commit.parents) != 1:
            raise ToolchainAssertion(f"Unexpected number of parents for {commit}")
        commit = commit.parents[0]
        if commit.committed_datetime < min_date:
            break
    return commits


def is_upstream_master_commit() -> bool:
    repo = Repo(".")
    upstream_master_commit = _get_upstream_master(repo)
    latest_commits = _get_parent_commits(upstream_master_commit, 5, utcnow() - datetime.timedelta(hours=1))
    commit_hashes = [cm.hexsha for cm in latest_commits]
    return repo.head.commit.hexsha in commit_hashes


def is_latest_upstream_master() -> bool:
    repo = Repo(".")
    upstream_master_commit = _get_upstream_master(repo)
    return repo.head.commit.hexsha == upstream_master_commit.hexsha


def has_local_changes() -> bool:
    repo = Repo(".")
    return bool(repo.index.diff(None) or repo.index.diff("HEAD") or repo.untracked_files)
