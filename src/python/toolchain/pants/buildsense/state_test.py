# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from defusedxml import ElementTree
from pants.goal.run_tracker import RunTrackerOptionEncoder

from toolchain.buildsense.test_utils.fixtures_loader import load_fixture
from toolchain.pants.auth.client import AuthState
from toolchain.pants.buildsense.client import BuildSenseRunInfo, RunEndInfo
from toolchain.pants.buildsense.common import RunTrackerBuildInfo, WorkUnits
from toolchain.pants.buildsense.converter_test import FakePantsContext, FakeSnapshot
from toolchain.pants.buildsense.state import BuildState, InvalidStateError, ReportOperation
from toolchain.util.test.util import assert_messages


class FakeBuildsenseClient:
    @classmethod
    def from_options(cls, client_options, auth, repo, org_name, base_url):
        return cls(fake_ci_user_api_id=None, base_url=f"{base_url}/api/v1/repos/")

    def __init__(self, fake_ci_user_api_id: str | None, base_url: str, plugin_config: dict | None = None) -> None:
        self._fake_ci_user_api_id = fake_ci_user_api_id
        self._run_start_calls: list[tuple[str, dict]] = []
        self._run_end_calls: list[tuple[str, str | None, dict]] = []
        self._workunits_calls: list[tuple[str, str | None, int, WorkUnits]] = []
        self._upload_artifact_calls: list[tuple[str, dict[str, bytes], str | None]] = []
        self._calls_to_fail: set[str] = set()
        self._auth_state = AuthState.OK
        self._submit_run_start_success = True
        self._plugin_config = plugin_config

    def is_auth_available(self) -> bool:
        return not self._auth_state.no_auth_possible

    def submit_run_start(self, *, run_id: str, build_stats: dict) -> BuildSenseRunInfo | None:
        self._run_start_calls.append((run_id, build_stats))
        if not self._submit_run_start_success:
            return None
        return BuildSenseRunInfo(ci_user_api_id=self._fake_ci_user_api_id, build_link="https://jerry.seinfeld/soup")

    def submit_run_end(self, *, run_id: str, user_api_id: str | None, build_stats: dict) -> RunEndInfo:
        self._run_end_calls.append((run_id, user_api_id, build_stats))
        data = json.dumps(build_stats, cls=RunTrackerOptionEncoder)
        return (
            RunEndInfo(success=False, data=data, build_link=None)
            if "submit_run_end" in self._calls_to_fail
            else RunEndInfo(success=True, data=data, build_link="https://jerry.seinfeld/soup")
        )

    def submit_workunits(self, *, run_id: str, call_num: int, user_api_id: str | None, workunits: WorkUnits):
        self._workunits_calls.append((run_id, user_api_id, call_num, workunits))

    def upload_artifacts(self, *, run_id, artifacts: dict[str, bytes], user_api_id: str | None) -> bool:
        self._upload_artifact_calls.append((run_id, artifacts, user_api_id))
        return "upload_artifacts" not in self._calls_to_fail

    def assert_no_calls(self):
        assert not self._run_start_calls
        assert not self._run_end_calls
        assert not self._workunits_calls
        assert not self._upload_artifact_calls

    def get_plugin_config(self) -> dict | None:
        return self._plugin_config

    def set_auth_state(self, state: AuthState) -> None:
        self._auth_state = state

    def set_submit_run_start_success(self, success: bool) -> None:
        self._submit_run_start_success = success

    def fail_on_call(self, call_name: str) -> None:
        self._calls_to_fail.add(call_name)

    @property
    def has_successful_calls(self) -> bool:
        return True

    @property
    def has_fake_user(self) -> bool:
        return bool(self._fake_ci_user_api_id)

    @property
    def run_start_calls(self):
        return self._run_start_calls

    @property
    def run_end_calls(self):
        return self._run_end_calls

    @property
    def workunits_calls(self):
        return self._workunits_calls

    @property
    def upload_artifact_calls(self):
        return self._upload_artifact_calls


class TestBuildState:
    def _load_build_stats(self, fixture: str, has_ended: bool, log_file: str | None = None) -> RunTrackerBuildInfo:
        return RunTrackerBuildInfo(has_ended=has_ended, build_stats=load_fixture(fixture), log_file=Path(log_file) if log_file else None)  # type: ignore

    @pytest.fixture(params=[True, False])
    def plugin_config(self, request) -> dict | None:
        if request.param is False:
            return None
        return {
            "config": {
                "work_units": {
                    "artifacts": ["stdout", "stderr", "xml_results"],
                    "metadata": ["exit_code", "definition", "source", "address", "addresses"],
                },
                "ci_capture": {
                    "CIRCLECI": r"^CIRCLE.*",
                    "TRAVIS": r"^TRAVIS.*",
                    "GITHUB_ACTIONS": r"^GITHUB.*",
                    "BITBUCKET_BUILD_NUMBER": r"^BITBUCKET.*",
                    "BUILDKITE": r"^BUILDKITE.*",
                },
            }
        }

    @pytest.fixture(params=[None, "ovaltine"])
    def fake_client(self, request, plugin_config: dict | None) -> FakeBuildsenseClient:
        return self._get_fake_client(ci_user_api_id=request.param, plugin_config=plugin_config)

    def _get_fake_client(self, ci_user_api_id: str | None, plugin_config: dict | None) -> FakeBuildsenseClient:
        return FakeBuildsenseClient(
            fake_ci_user_api_id=ci_user_api_id, base_url="https://chicken.com", plugin_config=plugin_config
        )

    @pytest.fixture()
    def build_state(self, tmp_path: Path, pants_context, fake_client) -> BuildState:
        build_state = BuildState(fake_client, tmp_path, 1, True, snapshot_type=FakeSnapshot)
        build_state.set_context(pants_context)
        return build_state

    @pytest.fixture()
    def pants_context(self) -> FakePantsContext:
        return FakePantsContext()

    def test_queue_and_send_initial_report(self, build_state: BuildState, fake_client) -> None:
        rt_info = self._load_build_stats("sample_9_start", has_ended=False)
        assert build_state.send_report() == ReportOperation.NO_OP
        build_state.queue_initial_report(rt_info)
        fake_client.assert_no_calls()
        assert build_state.send_report() == ReportOperation.SENT
        start_calls = fake_client.run_start_calls
        assert len(start_calls) == 1
        assert start_calls[0][0] == rt_info.run_id
        assert start_calls[0][1] == dict(rt_info.build_stats)

    def test_invalid_state(self, build_state: BuildState, fake_client: FakeBuildsenseClient) -> None:
        workunits = {"test1": {"span_id": "test1"}, "test2": {"span_id": "test2"}}
        with pytest.raises(InvalidStateError, match="run_id must be initialized."):
            build_state.queue_workunits(0, workunits)
        fake_client.assert_no_calls()

    def test_report_workunits_no_overrides(
        self, pants_context: FakePantsContext, build_state: BuildState, fake_client
    ) -> None:
        ts1 = int(time.time())
        ts0 = ts1 - 3
        rt_info_start = self._load_build_stats("sample_10_start", has_ended=False)
        wu_1 = pants_context.load_work_unit_fixture("work_units_test_53")
        wu_2 = pants_context.load_work_unit_fixture("work_units_test_65")
        duplicates = len(set(wu_1.keys()).intersection(wu_2.keys()))
        assert duplicates == 4  # sanity check
        assert build_state.send_report() == ReportOperation.NO_OP
        build_state.queue_initial_report(rt_info_start)
        build_state.queue_workunits(1, wu_1, ts0)
        build_state.queue_workunits(7, wu_2, ts1)
        fake_client.assert_no_calls()

        assert build_state.send_report() == ReportOperation.SENT
        assert len(fake_client.run_start_calls) == 1
        wu_calls = fake_client.workunits_calls
        assert len(wu_calls) == 1
        assert wu_calls[0][0] == rt_info_start.run_id
        if fake_client.has_fake_user:
            assert wu_calls[0][1] == "ovaltine"
        else:
            assert wu_calls[0][1] is None

        assert wu_calls[0][2] == 7
        reported_workunits = wu_calls[0][3]
        assert len(reported_workunits) == 15

    def test_report_workunits_no_overrides_with_race_condition(
        self, pants_context: FakePantsContext, build_state: BuildState, fake_client: FakeBuildsenseClient
    ) -> None:
        ts3 = int(time.time())
        ts2 = ts3 - 1
        ts1 = ts2 - 2
        rt_info_start = self._load_build_stats("sample_10_start", has_ended=False)
        wu_1 = pants_context.load_work_unit_fixture("work_units_test_2", level_override="INFO")
        wu_2 = pants_context.load_work_unit_fixture("work_units_test_53", level_override="INFO")
        wu_3 = pants_context.load_work_unit_fixture("work_units_test_65", level_override="INFO")
        duplicates = (len(wu_1) + len(wu_2) + len(wu_3)) - len(set(wu_1.keys()).union(wu_2.keys()).union(wu_3.keys()))
        assert duplicates == 10  # Sanity check
        assert len(set(wu_1.keys()).intersection(wu_2.keys())) == 6  # sanity check

        assert build_state.send_report() == ReportOperation.NO_OP
        build_state.queue_initial_report(rt_info_start)
        build_state.queue_workunits(1, wu_1, ts1)
        # This simulates a race condition in which then we start to dequeue there are two items in the queue (1 & 2).
        # But after we dequeue the last item (work_units_test_53) an item is added to the queue (work_units_test_65).
        build_state.queue_workunits(9, wu_3, ts3)
        build_state.queue_workunits(7, wu_2, ts2)
        fake_client.assert_no_calls()

        assert build_state.send_report() == ReportOperation.SENT
        assert len(fake_client.run_start_calls) == 1
        wu_calls = fake_client.workunits_calls
        assert len(wu_calls) == 1
        assert wu_calls[0][0] == rt_info_start.run_id
        if fake_client.has_fake_user:
            assert wu_calls[0][1] == "ovaltine"
        else:
            assert wu_calls[0][1] is None
        assert wu_calls[0][2] == 9
        reported_workunits = wu_calls[0][3]
        assert len(reported_workunits) == len(wu_1) + len(wu_2) + len(wu_3) - duplicates == 63 + 12 + 8 - 10

    def test_report_workunits_filtering(
        self, pants_context: FakePantsContext, build_state: BuildState, fake_client: FakeBuildsenseClient
    ) -> None:
        rt_info_start = self._load_build_stats("sample_10_start", has_ended=False)
        wu = pants_context.load_work_unit_fixture("work_units_fmt")
        assert build_state.send_report() == ReportOperation.NO_OP
        build_state.queue_initial_report(rt_info_start)
        build_state.queue_workunits(1, wu, timestamp=87111)
        assert build_state.send_report() == ReportOperation.SENT
        assert len(fake_client.workunits_calls) == 1
        reported_workunits = fake_client.workunits_calls[0][3]
        assert reported_workunits == [
            {
                "description": "Run Black on 10 targets: src/python/toolchain/pants/auth, "
                "src/python/toolchain/pants/auth:tests, "
                "src/python/toolchain/pants/buildgen, "
                "src/python/toolchain/pants/buildsense, "
                "src/python/toolchain/pants/buildsense:tests, "
                "src/python/toolchain/pants/common, "
                "src/python/toolchain/pants/internal, "
                "src/python/toolchain/pants/rules, "
                "src/python/toolchain/pants/rules:tests, "
                "src/python/toolchain/pants/util.",
                "end_usecs": 1596240164496976,
                "last_update": 87111,
                "name": "multi_platform_process-waiting",
                "parent_ids": ["ca049c4f0740fe7f"],
                "start_usecs": 1596240154473554,
                "state": "finished",
                "version": 1,
                "workunit_id": "b1d3673ea6c40618",
            },
            {
                "description": "Run Black on 10 targets: src/python/toolchain/pants/auth, "
                "src/python/toolchain/pants/auth:tests, "
                "src/python/toolchain/pants/buildgen, "
                "src/python/toolchain/pants/buildsense, "
                "src/python/toolchain/pants/buildsense:tests, "
                "src/python/toolchain/pants/common, "
                "src/python/toolchain/pants/internal, "
                "src/python/toolchain/pants/rules, "
                "src/python/toolchain/pants/rules:tests, "
                "src/python/toolchain/pants/util.",
                "end_usecs": 1596240164497683,
                "last_update": 87111,
                "name": "multi_platform_process",
                "parent_ids": ["1f08ed6189a3b66d"],
                "start_usecs": 1596240154472779,
                "state": "finished",
                "version": 1,
                "workunit_id": "ca049c4f0740fe7f",
            },
            {
                "end_usecs": 1596240164498451,
                "last_update": 87111,
                "name": "pants.engine.process.remove_platform_information",
                "parent_ids": ["a11f66436b6fcdb3"],
                "start_usecs": 1596240154472322,
                "state": "finished",
                "version": 1,
                "workunit_id": "1f08ed6189a3b66d",
            },
            {
                "end_usecs": 1596240164498518,
                "last_update": 87111,
                "name": "pants.engine.process.fallible_to_exec_result_or_raise",
                "parent_ids": ["b6ee1acacbcc6308"],
                "start_usecs": 1596240154472271,
                "state": "finished",
                "version": 1,
                "workunit_id": "a11f66436b6fcdb3",
            },
            {
                "description": "Format using Black",
                "end_usecs": 1596240164498997,
                "last_update": 87111,
                "name": "pants.backend.python.lint.black.rules.black_fmt",
                "parent_ids": ["dbe52f2a18ee4619"],
                "start_usecs": 1596240154413932,
                "state": "finished",
                "version": 1,
                "workunit_id": "b6ee1acacbcc6308",
            },
            {
                "end_usecs": 1596240166378753,
                "last_update": 87111,
                "name": "pants.backend.python.lint.python_fmt.format_python_target",
                "parent_ids": ["0bbaad48d9778005"],
                "start_usecs": 1596240154403068,
                "state": "finished",
                "version": 1,
                "workunit_id": "dbe52f2a18ee4619",
            },
            {
                "description": "`fmt` goal",
                "end_usecs": 1596240166406000,
                "last_update": 87111,
                "name": "fmt",
                "parent_ids": ["852304ed93fd6a1a"],
                "start_usecs": 1596240154346112,
                "state": "finished",
                "version": 1,
                "workunit_id": "0bbaad48d9778005",
            },
            {
                "last_update": 87111,
                "name": "select",
                "parent_ids": [],
                "start_usecs": 1596240154345821,
                "state": "started",
                "version": 1,
                "workunit_id": "852304ed93fd6a1a",
            },
            {
                "description": "Run Black on 10 targets: src/python/toolchain/pants/auth, "
                "src/python/toolchain/pants/auth:tests, "
                "src/python/toolchain/pants/buildgen, "
                "src/python/toolchain/pants/buildsense, "
                "src/python/toolchain/pants/buildsense:tests, "
                "src/python/toolchain/pants/common, "
                "src/python/toolchain/pants/internal, "
                "src/python/toolchain/pants/rules, "
                "src/python/toolchain/pants/rules:tests, "
                "src/python/toolchain/pants/util.",
                "end_usecs": 1596240164496962,
                "last_update": 87111,
                "name": "multi_platform_process-running",
                "parent_ids": ["b1d3673ea6c40618"],
                "start_usecs": 1596240154473567,
                "state": "finished",
                "version": 1,
                "workunit_id": "bcade4ad58004175",
            },
            {
                "description": "Run Docformatter on 10 targets: "
                "src/python/toolchain/pants/auth, "
                "src/python/toolchain/pants/auth:tests, "
                "src/python/toolchain/pants/buildgen, "
                "src/python/toolchain/pants/buildsense, "
                "src/python/toolchain/pants/buildsense:tests, "
                "src/python/toolchain/pants/common, "
                "src/python/toolchain/pants/internal, "
                "src/python/toolchain/pants/rules, "
                "src/python/toolchain/pants/rules:tests, "
                "src/python/toolchain/pants/util.",
                "end_usecs": 1596240165491016,
                "last_update": 87111,
                "name": "multi_platform_process-waiting",
                "parent_ids": ["6d44103fc48d15d2"],
                "start_usecs": 1596240164507432,
                "state": "finished",
                "version": 1,
                "workunit_id": "bd594994bb087a6f",
            },
            {
                "description": "Run Docformatter on 10 targets: "
                "src/python/toolchain/pants/auth, "
                "src/python/toolchain/pants/auth:tests, "
                "src/python/toolchain/pants/buildgen, "
                "src/python/toolchain/pants/buildsense, "
                "src/python/toolchain/pants/buildsense:tests, "
                "src/python/toolchain/pants/common, "
                "src/python/toolchain/pants/internal, "
                "src/python/toolchain/pants/rules, "
                "src/python/toolchain/pants/rules:tests, "
                "src/python/toolchain/pants/util.",
                "end_usecs": 1596240165491515,
                "last_update": 87111,
                "name": "multi_platform_process",
                "parent_ids": ["a84229df6a491777"],
                "start_usecs": 1596240164506479,
                "state": "finished",
                "version": 1,
                "workunit_id": "6d44103fc48d15d2",
            },
            {
                "end_usecs": 1596240165491781,
                "last_update": 87111,
                "name": "pants.engine.process.remove_platform_information",
                "parent_ids": ["099deef080116fc8"],
                "start_usecs": 1596240164506104,
                "state": "finished",
                "version": 1,
                "workunit_id": "a84229df6a491777",
            },
            {
                "end_usecs": 1596240165491840,
                "last_update": 87111,
                "name": "pants.engine.process.fallible_to_exec_result_or_raise",
                "parent_ids": ["1b9ec852ab38f8e9"],
                "start_usecs": 1596240164506057,
                "state": "finished",
                "version": 1,
                "workunit_id": "099deef080116fc8",
            },
            {
                "description": "Format Python docstrings with docformatter",
                "end_usecs": 1596240165491967,
                "last_update": 87111,
                "name": "pants.backend.python.lint.docformatter.rules.docformatter_fmt",
                "parent_ids": ["dbe52f2a18ee4619"],
                "start_usecs": 1596240164500458,
                "state": "finished",
                "version": 1,
                "workunit_id": "1b9ec852ab38f8e9",
            },
            {
                "description": "Run Docformatter on 10 targets: "
                "src/python/toolchain/pants/auth, "
                "src/python/toolchain/pants/auth:tests, "
                "src/python/toolchain/pants/buildgen, "
                "src/python/toolchain/pants/buildsense, "
                "src/python/toolchain/pants/buildsense:tests, "
                "src/python/toolchain/pants/common, "
                "src/python/toolchain/pants/internal, "
                "src/python/toolchain/pants/rules, "
                "src/python/toolchain/pants/rules:tests, "
                "src/python/toolchain/pants/util.",
                "end_usecs": 1596240165491005,
                "last_update": 87111,
                "name": "multi_platform_process-running",
                "parent_ids": ["bd594994bb087a6f"],
                "start_usecs": 1596240164507445,
                "state": "finished",
                "version": 1,
                "workunit_id": "b7fb9095ea0a7c83",
            },
            {
                "description": "Run isort on 10 targets: src/python/toolchain/pants/auth, "
                "src/python/toolchain/pants/auth:tests, "
                "src/python/toolchain/pants/buildgen, "
                "src/python/toolchain/pants/buildsense, "
                "src/python/toolchain/pants/buildsense:tests, "
                "src/python/toolchain/pants/common, "
                "src/python/toolchain/pants/internal, "
                "src/python/toolchain/pants/rules, "
                "src/python/toolchain/pants/rules:tests, "
                "src/python/toolchain/pants/util.",
                "end_usecs": 1596240166378042,
                "last_update": 87111,
                "name": "multi_platform_process-waiting",
                "parent_ids": ["81aa6c91e792c5e5"],
                "start_usecs": 1596240165500490,
                "state": "finished",
                "version": 1,
                "workunit_id": "e465883a136e2e45",
            },
            {
                "description": "Run isort on 10 targets: src/python/toolchain/pants/auth, "
                "src/python/toolchain/pants/auth:tests, "
                "src/python/toolchain/pants/buildgen, "
                "src/python/toolchain/pants/buildsense, "
                "src/python/toolchain/pants/buildsense:tests, "
                "src/python/toolchain/pants/common, "
                "src/python/toolchain/pants/internal, "
                "src/python/toolchain/pants/rules, "
                "src/python/toolchain/pants/rules:tests, "
                "src/python/toolchain/pants/util.",
                "end_usecs": 1596240166378252,
                "last_update": 87111,
                "name": "multi_platform_process",
                "parent_ids": ["736463b468c59ace"],
                "start_usecs": 1596240165499606,
                "state": "finished",
                "version": 1,
                "workunit_id": "81aa6c91e792c5e5",
            },
            {
                "end_usecs": 1596240166378509,
                "last_update": 87111,
                "name": "pants.engine.process.remove_platform_information",
                "parent_ids": ["264feb65641c4ea8"],
                "start_usecs": 1596240165499276,
                "state": "finished",
                "version": 1,
                "workunit_id": "736463b468c59ace",
            },
            {
                "end_usecs": 1596240166378551,
                "last_update": 87111,
                "name": "pants.engine.process.fallible_to_exec_result_or_raise",
                "parent_ids": ["9ee8e4028fe83985"],
                "start_usecs": 1596240165499236,
                "state": "finished",
                "version": 1,
                "workunit_id": "264feb65641c4ea8",
            },
            {
                "description": "Format using isort",
                "end_usecs": 1596240166378670,
                "last_update": 87111,
                "name": "pants.backend.python.lint.isort.rules.isort_fmt",
                "parent_ids": ["dbe52f2a18ee4619"],
                "start_usecs": 1596240165492602,
                "state": "finished",
                "version": 1,
                "workunit_id": "9ee8e4028fe83985",
            },
            {
                "description": "Run isort on 10 targets: src/python/toolchain/pants/auth, "
                "src/python/toolchain/pants/auth:tests, "
                "src/python/toolchain/pants/buildgen, "
                "src/python/toolchain/pants/buildsense, "
                "src/python/toolchain/pants/buildsense:tests, "
                "src/python/toolchain/pants/common, "
                "src/python/toolchain/pants/internal, "
                "src/python/toolchain/pants/rules, "
                "src/python/toolchain/pants/rules:tests, "
                "src/python/toolchain/pants/util.",
                "end_usecs": 1596240166378028,
                "last_update": 87111,
                "name": "multi_platform_process-running",
                "parent_ids": ["e465883a136e2e45"],
                "start_usecs": 1596240165500498,
                "state": "finished",
                "version": 1,
                "workunit_id": "36cb5c7a4de18266",
            },
        ]

    def test_report_workunits_with_artifacts(
        self, pants_context: FakePantsContext, build_state: BuildState, fake_client: FakeBuildsenseClient
    ) -> None:
        rt_info_start = self._load_build_stats("sample_10_start", has_ended=False)
        rt_info_end = self._load_build_stats("sample_10_finish", has_ended=True)
        wu = pants_context.load_work_unit_fixture("work_units_fmt")
        assert len(wu) == 228  # Sanity check
        assert build_state.send_report() == ReportOperation.NO_OP
        build_state.queue_initial_report(rt_info_start)
        build_state.queue_workunits(1, wu)
        assert build_state.send_report() == ReportOperation.SENT
        assert len(fake_client.workunits_calls) == 1
        build_state.submit_final_report(rt_info_end, 3)
        build_state.send_final_report()

        assert len(fake_client.run_end_calls) == 1
        final_report = fake_client.run_end_calls[0][2]
        assert len(final_report["workunits"]) == 228
        all_work_units_map = {wu["workunit_id"]: wu for wu in final_report["workunits"]}
        black_wu = all_work_units_map["bcade4ad58004175"]
        black_artifacts = black_wu["artifacts"]
        assert len(black_artifacts) == 1
        assert (
            black_artifacts["stderr"]
            == "reformatted /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executionpCqBCe/src/python/toolchain/pants/buildsense/local_store.py\nreformatted /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executionpCqBCe/src/python/toolchain/pants/buildsense/local_store_test.py\nAll done! ✨ 🍰 ✨\n2 files reformatted, 32 files left unchanged.\n"
        )
        assert fake_client.upload_artifact_calls == []

    def test_work_units_on_final_call(
        self, pants_context: FakePantsContext, build_state: BuildState, fake_client: FakeBuildsenseClient
    ) -> None:
        rt_info_start = self._load_build_stats("sample_10_start", has_ended=False)
        rt_info_end = self._load_build_stats("sample_10_finish", has_ended=True)
        wu = pants_context.load_work_unit_fixture("work_units_fmt")
        assert build_state.send_report() == ReportOperation.NO_OP
        build_state.queue_initial_report(rt_info_start)
        build_state.queue_workunits(1, wu)
        build_state.submit_final_report(rt_info_end, 3)
        build_state.send_final_report()
        final_report = fake_client.run_end_calls[0][2]
        assert len(final_report["workunits"]) == 228
        assert fake_client.upload_artifact_calls == []

    def test_artifacts_upload_on_final_call(
        self, pants_context: FakePantsContext, build_state: BuildState, fake_client: FakeBuildsenseClient
    ) -> None:
        rt_info_start = self._load_build_stats("sample_10_start", has_ended=False)
        rt_info_end = self._load_build_stats("sample_10_finish", has_ended=True)
        wu = pants_context.load_work_unit_fixture("pytest_with_coverage_xml")
        assert build_state.send_report() == ReportOperation.NO_OP
        build_state.queue_initial_report(rt_info_start)
        build_state.queue_workunits(1, wu)
        build_state.submit_final_report(rt_info_end, 3)
        build_state.send_final_report()
        final_report = fake_client.run_end_calls[0][2]
        assert len(final_report["workunits"]) == 8
        assert len(fake_client.upload_artifact_calls) == 1
        upload_artifact_call = fake_client.upload_artifact_calls[0]
        assert upload_artifact_call[0] == "pants_run_2020_01_28_17_50_13_106_c4c0a8c0235447a49facd0f338cce581"
        assert upload_artifact_call[2] is None
        artifacts = upload_artifact_call[1]
        assert len(artifacts) == 2
        descriptors = json.loads(artifacts["descriptors.json"])
        assert len(descriptors) == 1
        key = list(descriptors.keys())[0]
        assert descriptors == {
            key: {
                "workunit_id": "c87d0fa47a708e99",
                "name": "coverage_xml",
                "path": "coverage.xml",
            }
        }
        coverage_xml = ElementTree.fromstring(artifacts[key])
        assert coverage_xml.tag == "coverage"

    def test_artifacts_upload_log_on_final_call(
        self,
        tmp_path: Path,
        pants_context: FakePantsContext,
        build_state: BuildState,
        fake_client: FakeBuildsenseClient,
    ) -> None:
        log_file_name = tmp_path / "fake_pants_run_log.txt"
        log_file_name.write_bytes(b"He called me big head.\nIt is almost a complement")
        rt_info_start = self._load_build_stats("run_with_pex_failure", has_ended=False)
        rt_info_end = self._load_build_stats("run_with_pex_failure", has_ended=True, log_file=str(log_file_name))
        wu = pants_context.load_work_unit_fixture("pytest_with_coverage_xml")
        assert build_state.send_report() == ReportOperation.NO_OP
        build_state.queue_initial_report(rt_info_start)
        build_state.queue_workunits(1, wu)
        build_state.submit_final_report(rt_info_end, 3)
        build_state.send_final_report()
        final_report = fake_client.run_end_calls[0][2]
        assert len(final_report["workunits"]) == 8
        assert len(fake_client.upload_artifact_calls) == 1
        upload_artifact_call = fake_client.upload_artifact_calls[0]
        assert upload_artifact_call[0] == "pants_run_2020_10_13_10_45_53_495_c60f37108a5f4b709312649ced9cca2a"
        assert upload_artifact_call[2] is None
        artifacts = upload_artifact_call[1]
        assert len(artifacts) == 3
        descriptors = json.loads(artifacts["descriptors.json"])
        assert len(descriptors) == 1
        key = list(descriptors.keys())[0]
        assert descriptors == {
            key: {
                "workunit_id": "c87d0fa47a708e99",
                "name": "coverage_xml",
                "path": "coverage.xml",
            }
        }
        coverage_xml = ElementTree.fromstring(artifacts[key])
        assert coverage_xml.tag == "coverage"
        assert "pants_run_log" in artifacts
        assert artifacts["pants_run_log"] == b"He called me big head.\nIt is almost a complement"

    def test_artifacts_upload_log_only(
        self,
        tmp_path: Path,
        pants_context: FakePantsContext,
        build_state: BuildState,
        fake_client: FakeBuildsenseClient,
    ) -> None:
        log_file_name = tmp_path / "fake_pants_run_log.txt"
        log_file_name.write_bytes(b"I didn't get any bread.\nJust forget it let it go.")
        rt_info_start = self._load_build_stats("run_with_pex_failure", has_ended=False)
        rt_info_end = self._load_build_stats("run_with_pex_failure", has_ended=True, log_file=str(log_file_name))
        wu = pants_context.load_work_unit_fixture("work_units_fmt")
        assert build_state.send_report() == ReportOperation.NO_OP
        build_state.queue_initial_report(rt_info_start)
        build_state.queue_workunits(1, wu)
        build_state.submit_final_report(rt_info_end, 3)
        build_state.send_final_report()
        final_report = fake_client.run_end_calls[0][2]
        assert len(final_report["workunits"]) == 228
        assert len(fake_client.upload_artifact_calls) == 1
        upload_artifact_call = fake_client.upload_artifact_calls[0]
        assert upload_artifact_call[0] == "pants_run_2020_10_13_10_45_53_495_c60f37108a5f4b709312649ced9cca2a"
        assert upload_artifact_call[2] is None
        artifacts = upload_artifact_call[1]
        assert len(artifacts) == 1
        assert "pants_run_log" in artifacts
        assert artifacts["pants_run_log"] == b"I didn't get any bread.\nJust forget it let it go."

    def test_store_on_build_upload_fail(
        self,
        tmp_path: Path,
        pants_context: FakePantsContext,
        build_state: BuildState,
        fake_client: FakeBuildsenseClient,
    ) -> None:
        fake_client.fail_on_call("submit_run_end")
        rt_info_start = self._load_build_stats("sample_10_start", has_ended=False)
        rt_info_end = self._load_build_stats("sample_10_finish", has_ended=True)
        wu = pants_context.load_work_unit_fixture("work_units_fmt")
        assert build_state.send_report() == ReportOperation.NO_OP
        build_state.queue_initial_report(rt_info_start)
        build_state.queue_workunits(1, wu)
        build_state.submit_final_report(rt_info_end, 3)
        build_state.send_final_report()
        queued_build_file = tmp_path / "queue" / "build_stats" / f"{rt_info_end.run_id}.json"
        assert queued_build_file.exists()
        queued_build = json.loads(queued_build_file.read_bytes())
        assert set(queued_build.keys()) == {
            "run_info",
            "artifact_cache_stats",
            "pantsd_stats",
            "workunits",
            "recorded_options",
            "cumulative_timings",
        }
        final_report = fake_client.run_end_calls[0][2]
        assert len(final_report["workunits"]) == 228
        assert fake_client.upload_artifact_calls == []

    @pytest.mark.parametrize("auth_state", [AuthState.FAILED, AuthState.UNAVAILABLE])
    def test_no_op_send_report_when_auth_failed(
        self,
        tmp_path: Path,
        caplog,
        auth_state: AuthState,
        pants_context: FakePantsContext,
        build_state: BuildState,
        fake_client: FakeBuildsenseClient,
    ) -> None:
        fake_client.set_auth_state(auth_state)
        rt_info_start = self._load_build_stats("sample_10_start", has_ended=False)
        wu = pants_context.load_work_unit_fixture("work_units_fmt")
        assert build_state.send_report() == ReportOperation.ERROR
        build_state.queue_initial_report(rt_info_start)
        build_state.queue_workunits(1, wu)
        assert build_state.send_report() == ReportOperation.ERROR
        fake_client.assert_no_calls()
        assert build_state._sent_initial_report is False
        assert_messages(caplog, "Auth failed - BuildSense plugin is disabled")

    def test_sumbit_run_start_fail(
        self,
        tmp_path: Path,
        caplog,
        pants_context: FakePantsContext,
        build_state: BuildState,
        fake_client: FakeBuildsenseClient,
    ) -> None:
        fake_client.set_submit_run_start_success(False)
        rt_info_start = self._load_build_stats("sample_10_start", has_ended=False)
        assert build_state.send_report() == ReportOperation.NO_OP
        assert build_state._sent_initial_report is False
        fake_client.assert_no_calls()

        build_state.queue_initial_report(rt_info_start)
        assert build_state.send_report() == ReportOperation.ERROR
        assert build_state._sent_initial_report is False
        assert len(fake_client.run_start_calls) == 1
        fake_client.set_submit_run_start_success(True)

        assert build_state.send_report() == ReportOperation.SENT
        assert build_state._sent_initial_report is True
        assert len(fake_client.run_start_calls) == 2
