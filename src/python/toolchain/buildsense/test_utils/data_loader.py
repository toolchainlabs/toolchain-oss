# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

from toolchain.base.datetime_tools import utcnow
from toolchain.buildsense.ingestion.pants_data_ingestion import RequestContext
from toolchain.buildsense.records.run_info import RunInfo, ScmProvider, ServerInfo
from toolchain.buildsense.test_utils.data_parser import parse_run_info
from toolchain.buildsense.test_utils.fixtures_loader import load_fixture


def insert_build_data(
    pdi, build_data: dict, user, server_info: ServerInfo, add_scm_link: ScmProvider | None = None
) -> tuple[bool, RunInfo]:
    run_info = parse_run_info(
        fixture_data=build_data,
        repo=pdi._repo,
        user=user,
        server_info=server_info,
        add_scm_link=add_scm_link,
    )
    return pdi._table.save_run(run_info), run_info


def load_run_info(fixture_name: str, repo, user) -> RunInfo:
    server_info = ServerInfo(
        request_id="test-save-run",
        accept_time=utcnow(),
        stats_version="3",
        environment="low-flow",
        s3_bucket="chicken",
        s3_key="little-jerry-seinfeld",
    )
    build_data = load_fixture(fixture_name)
    return parse_run_info(fixture_data=build_data, repo=repo, user=user, server_info=server_info)


def get_fake_request_context(
    stats_version: str = "3", request_id: str = "fake-req-id", accept_time: datetime.datetime | None = None
) -> RequestContext:
    return RequestContext(
        stats_version=stats_version,
        request_id=request_id,
        accept_time=accept_time or utcnow(),
        client_ip=None,
        content_length=230_300_200,
    )
