# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# This pylint ignore is due to the migration of the pants options API, when we remove backward compatibility we should also remove this line
# pylint: disable=unexpected-keyword-arg
from __future__ import annotations

import logging

from pants.engine.rules import Get, collect_rules, rule
from pants.engine.streaming_workunit_handler import WorkunitsCallbackFactory, WorkunitsCallbackFactoryRequest
from pants.engine.unions import UnionRule
from pants.vcs.git import GitWorktreeRequest, MaybeGitWorktree

# Renamed in 2.15.x.
try:
    from pants.engine.env_vars import CompleteEnvironmentVars
except ImportError:
    from pants.engine.environment import CompleteEnvironment as CompleteEnvironmentVars  # type: ignore

from toolchain.pants.auth.store import AuthStore
from toolchain.pants.buildsense.reporter import Reporter, ReporterCallback
from toolchain.pants.common.toolchain_setup import ToolchainSetup

logger = logging.getLogger(__name__)


class BuildsenseCallbackFactoryRequest:
    """A unique request type that is installed to trigger construction of our WorkunitsCallback."""


@rule
async def construct_buildsense_callback(
    _: BuildsenseCallbackFactoryRequest,
    reporter: Reporter,
    toolchain_setup: ToolchainSetup,
    auth_store: AuthStore,
    environment: CompleteEnvironmentVars,
) -> WorkunitsCallbackFactory:
    repo_name = toolchain_setup.safe_get_repo_name()
    maybe_gwt = await Get(MaybeGitWorktree, GitWorktreeRequest())
    git_worktree = maybe_gwt.git_worktree

    return WorkunitsCallbackFactory(
        lambda: ReporterCallback(
            reporter,
            auth_store=auth_store,
            env=dict(environment),
            repo_name=repo_name,
            org_name=toolchain_setup.org_name,
            base_url=toolchain_setup.base_url,
            git_worktree=git_worktree,
        )
    )


def rules_buildsense_reporter():
    return [
        UnionRule(WorkunitsCallbackFactoryRequest, BuildsenseCallbackFactoryRequest),
        *collect_rules(),
    ]
