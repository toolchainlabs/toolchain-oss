# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from unittest.mock import MagicMock

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.buildsense.ingestion.integrations.ci_integration import get_ci_info
from toolchain.buildsense.records.adapters import from_post_data
from toolchain.buildsense.records.run_info import RunInfo, ScmProvider, ServerInfo


def create_run_info(build_stats: dict, stats_version: str) -> RunInfo:
    repo = MagicMock(customer_id="festivus", pk="pole")
    user = MagicMock(api_id="soup")
    server_info = ServerInfo(
        request_id="tinsel",
        accept_time=utcnow(),
        stats_version=stats_version,
        environment="low-flow",
        s3_bucket="chicken",
        s3_key="little-jerry-seinfeld",
    )
    return parse_run_info(fixture_data=build_stats, repo=repo, user=user, server_info=server_info)


def parse_run_info(*, fixture_data, repo, user, server_info, add_scm_link: ScmProvider | None = None) -> RunInfo:
    run_info_json = dict(fixture_data["run_info"])
    run_id = run_info_json.pop("id")
    fixture_data.pop("ci_info", None)
    full_ci_details = get_ci_info(fixture_data.get("ci_env"), context=f"tests for {run_id=}")
    if add_scm_link and full_ci_details:
        if add_scm_link == ScmProvider.GITHUB:
            full_ci_details.details.link = "https://github.com/toolchainlabs/toolchain/"
        elif add_scm_link == ScmProvider.BITBUCKET:
            full_ci_details.details.link = "https://bitbucket.org/festivus-miracle/minimal-pants/src/main/"
        else:
            raise ToolchainAssertion(f"Unknown scm provider: {add_scm_link=}")
    run_info = from_post_data(
        run_id=run_id,
        run_info_json=run_info_json,
        repo=repo,
        user=user,
        server_info=server_info,
        ci_details=full_ci_details.details if full_ci_details else None,
    )
    run_info.collected_platform_info = "platform" in fixture_data
    if full_ci_details:
        run_info.title = "No soup for you come back one year!"
    return run_info
