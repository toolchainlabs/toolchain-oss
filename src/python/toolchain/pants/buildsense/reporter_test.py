# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, cast
from unittest import mock

import pytest
from faker import Faker
from pants.engine.streaming_workunit_handler import ExpandedSpecs, TargetInfo
from pants.testutil.option_util import create_subsystem

from toolchain.buildsense.test_utils.fixtures_loader import load_fixture
from toolchain.pants.auth.client import AuthState
from toolchain.pants.auth.client_test import TEST_TOKEN_STRING
from toolchain.pants.auth.rules import AuthStoreOptions
from toolchain.pants.auth.store import AuthStore
from toolchain.pants.auth.token import AuthToken
from toolchain.pants.buildsense.converter_test import load_local_fixture
from toolchain.pants.buildsense.reporter import CaptureCIEnv, Reporter, ReporterCallback
from toolchain.pants.buildsense.state_test import FakeBuildsenseClient, assert_messages


class FakeAuthStore(AuthStore):
    @classmethod
    def create(cls, env: Mapping[str, str], repo: str | None, base_url: str) -> FakeAuthStore:
        auth_store = create_subsystem(
            AuthStoreOptions,
            org=None,
            auth_file=None,
            from_env_var=None,
            ci_env_variables=tuple(),  # type: ignore[arg-type]
            restricted_token_matches=dict(),
            token_expiration_threshold=30,
        )
        return cls(
            context="test-fake",
            options=auth_store.options,
            pants_bin_name="pants",
            env=env,
            repo=repo,
            base_url=f"{base_url}/api/v1/repos/",
        )

    def get_auth_state(self) -> AuthState:
        return AuthState.OK

    def get_access_token(self) -> AuthToken:
        return AuthToken.from_access_token_string(TEST_TOKEN_STRING)


class FakeRunTracker:
    def __init__(self, tmp_path: Path) -> None:
        self._has_ended = False
        self._log_path = tmp_path / "roundtine.log"
        self.pantsd_scheduler_metrics = {
            "affected_file_count": 2306,
            "affected_targets_size": 0,
            "preceding_graph_size": 0,
            "resulting_graph_size": 22647,
            "target_root_size": 0,
        }

    def has_ended(self) -> bool:
        return self._has_ended

    def mark_ended(self, disable_log: bool = False) -> None:
        self._has_ended = True
        if disable_log:
            return
        faker = Faker()
        log_data = "\n".join(faker.paragraph(nb_sentences=3) for _ in range(10))
        self._log_path.write_text(log_data, encoding="utf-8")

    @property
    def run_logs_file(self) -> str | None:
        return self._log_path.as_posix() if self._has_ended and self._log_path.exists() else None

    @property
    def goals(self) -> list[str]:
        return ["gold", "jerry"]

    def run_information(self) -> dict:
        data = {"id": "no-soup-for-you-come-back-one-year"}
        if self._has_ended:
            data.update({"outcome": "SUCCESS"})
        return data

    def get_options_to_record(self) -> dict:
        return {"newman": ["usps"], "GLOBAL": {"level": "info"}}

    def get_cumulative_timings(self):
        return [
            {"label": "main", "timing": 300, "is_tool": False},
            {"label": "main:complete", "timing": 12, "is_tool": False},
        ]

    @property
    def counter_names(self) -> tuple[str, ...]:
        return ("puffy", "shirt")


def _work_units_fmt_stats(run_info, *, with_histograms=True):
    return {
        "run_info": run_info,
        "recorded_options": {"newman": ["usps"], "GLOBAL": {"level": "info"}},
        "pantsd_stats": {
            "affected_file_count": 2306,
            "affected_targets_size": 0,
            "preceding_graph_size": 0,
            "resulting_graph_size": 22647,
            "target_root_size": 0,
        },
        "counter_names": ["puffy", "shirt"],
        "targets": {
            "src/python/toolchain/users/workers": [
                {"filename": "src/python/toolchain/users/workers/periodic_access_tokens_checker.py"},
                {"filename": "src/python/toolchain/users/workers/users_worker.py"},
            ],
            "src/python/toolchain/users/workers:tests": [
                {"filename": "src/python/toolchain/users/workers/conftest.py"},
                {"filename": "src/python/toolchain/users/workers/periodic_access_tokens_checker_test.py"},
            ],
        },
        "cumulative_timings": [
            {"label": "main", "timing": 300, "is_tool": False},
            {"label": "main:complete", "timing": 12, "is_tool": False},
        ],
        **(
            {
                "observation_histograms": {
                    "version": 0,
                    "histograms": {
                        "test_observation": "dGhpcy53b3VsZC5iZS5iYXNlNjQuZW5jb2RlZC5ieXRlcw==",
                    },
                }
            }
            if with_histograms
            else {}
        ),
        "counters": {
            "metric_one": 1,
        },
    }


@dataclass(frozen=True)
class FakeWorkunitContext:
    run_tracker: FakeRunTracker
    observation_histograms: dict[str, Any]
    metrics: dict[str, int]

    @classmethod
    def create(cls, tmp_path: Path) -> FakeWorkunitContext:
        return cls(
            run_tracker=FakeRunTracker(tmp_path),
            observation_histograms={
                "version": 0,
                "histograms": {
                    "test_observation": b"this.would.be.base64.encoded.bytes",
                },
            },
            metrics={
                "metric_one": 1,
            },
        )

    def set_histogram_version(self, version: int) -> None:
        self.observation_histograms["version"] = version  # type: ignore[index]

    def mark_ended(self, disable_log: bool = False) -> None:
        self.run_tracker.mark_ended(disable_log)

    def clear_histograms(self) -> None:
        self.observation_histograms["histograms"] = {}

    def get_observation_histograms(self) -> dict[str, Any] | None:
        return self.observation_histograms

    def get_expanded_specs(self) -> ExpandedSpecs:
        return ExpandedSpecs(
            targets={
                "src/python/toolchain/users/workers": [
                    TargetInfo(filename="src/python/toolchain/users/workers/periodic_access_tokens_checker.py"),
                    TargetInfo(filename="src/python/toolchain/users/workers/users_worker.py"),
                ],
                "src/python/toolchain/users/workers:tests": [
                    TargetInfo(filename="src/python/toolchain/users/workers/conftest.py"),
                    TargetInfo(filename="src/python/toolchain/users/workers/periodic_access_tokens_checker_test.py"),
                ],
            }
        )

    def get_metrics(self) -> dict[str, int]:
        return self.metrics


def fake_get_host_name() -> str:
    return "wilhelm"


def fake_is_docker() -> bool:
    return True


@mock.patch("toolchain.pants.buildsense.reporter.socket.gethostname", new=fake_get_host_name)
@mock.patch("toolchain.pants.buildsense.reporter._is_docker", new=fake_is_docker)
@mock.patch("toolchain.pants.buildsense.reporter.BuildSenseClient", new=FakeBuildsenseClient)
class TestReporter:
    @pytest.fixture(params=["WITH_GIT", "WITHOUT_GIT"])
    def with_git(self, request) -> bool:
        return request.param == "WITH_GIT"

    def get_expected_run_info(self, with_git: bool, outcome: str) -> dict:
        run_info_data = {
            "id": "no-soup-for-you-come-back-one-year",
            "outcome": outcome,
            "machine": "wilhelm [docker]",
            "computed_goals": ["gold", "jerry"],
        }
        if with_git:
            run_info_data.update({"revision": "babka", "branch": "chocolate"})
        return run_info_data

    def _get_reporter(
        self,
        tmp_path: Path,
        ci_env_pattern: str | None = None,
        env: Mapping[str, str] | None = None,
        repo_name: str | None = None,
        org_name: str | None = None,
        collect_platform_data: bool = False,
        with_git: bool = True,
    ) -> ReporterCallback:
        reporter = create_subsystem(
            Reporter,
            timeout=1,
            dry_run=True,
            local_store_base=tmp_path.as_posix(),
            max_batch_size_mb=20,
            local_build_store=False,
            log_final_upload_latency=True,
            ci_env_var_pattern=ci_env_pattern,
            ci_env_scrub_terms=list(CaptureCIEnv.DEFAULT_EXCLUDE_TERMS),
            enable=True,
            log_upload=True,
            show_link=True,
            collect_platform_data=collect_platform_data,
        )
        env = env or {}
        base_url = "http://soup.com"
        scm = mock.MagicMock(commit_id="babka", branch_name="chocolate") if with_git else None
        return ReporterCallback(
            options=reporter.options,
            auth_store=FakeAuthStore.create(env, repo_name, base_url=base_url),
            env=env,
            repo_name=repo_name,
            base_url=base_url,
            org_name=org_name,
            git_worktree=scm,
        )

    @pytest.fixture()
    def pants_context(self, tmp_path: Path) -> FakeWorkunitContext:
        return FakeWorkunitContext.create(tmp_path)

    @pytest.fixture(params=["", "festivus"])
    def org_name(self, request) -> str:
        return request.param

    def test_disabled_no_repo(self, tmp_path: Path, org_name: str, with_git: bool) -> None:
        reporter = self._get_reporter(tmp_path, repo_name=None, org_name=org_name, with_git=with_git)
        assert reporter._enabled is False

    def test_handle_work_units_initial_empty(self, tmp_path: Path, org_name: str, with_git: bool) -> None:
        reporter = self._get_reporter(tmp_path, repo_name="ovaltine", org_name=org_name, with_git=with_git)
        reporter(
            completed_workunits=[], started_workunits=[], context=FakeWorkunitContext.create(tmp_path), finished=False  # type: ignore[arg-type]
        )
        assert reporter._enabled is True
        build_state = reporter._build_state
        assert build_state is not None
        assert build_state._run_id == "no-soup-for-you-come-back-one-year"

    def test_handle_work_units_under_ci(self, tmp_path: Path, org_name: str, with_git: bool) -> None:
        reporter = self._get_reporter(
            tmp_path,
            r"^FESTIVUS.*",
            env={
                "FESTIVUS_TINEL": "I find tinsel distracting",
                "FESTIVUS_GEORGE": "kookie-talk",
                "FESTIVUS_JANET": "looks-like-jerry",
                "JANET_FESTIVUS": "peterman",
            },
            repo_name="ovaltine",
            org_name=org_name,
            with_git=with_git,
        )
        reporter(
            completed_workunits=[], started_workunits=[], context=FakeWorkunitContext.create(tmp_path), finished=False  # type: ignore[arg-type]
        )
        assert reporter._enabled is True
        assert reporter._build_state is not None
        report = reporter._build_state._initial_report
        assert report is not None
        assert report.has_ended is False
        assert report.build_stats["ci_env"] == {
            "FESTIVUS_TINEL": "I find tinsel distracting",
            "FESTIVUS_GEORGE": "kookie-talk",
            "FESTIVUS_JANET": "looks-like-jerry",
        }

    def test_start_and_finished(
        self,
        with_git: bool,
        tmp_path: Path,
        pants_context: FakeWorkunitContext,
        org_name: str,
    ) -> None:
        workunits = load_local_fixture("work_units_fmt")
        reporter = self._get_reporter(tmp_path, repo_name="ovaltine", org_name=org_name, with_git=with_git)
        assert reporter._call_count == 0
        reporter(completed_workunits=workunits, started_workunits=[], context=pants_context, finished=False)  # type: ignore[arg-type]
        assert reporter._call_count == 1
        assert reporter._enabled is True
        state = reporter._build_state
        assert state._end_report_data is None
        assert state._run_id == "no-soup-for-you-come-back-one-year"
        initial_report = state._initial_report
        assert initial_report is not None
        assert initial_report.has_ended is False
        assert initial_report.log_file is None
        assert initial_report.build_stats == {
            "run_info": self.get_expected_run_info(with_git, "NOT_AVAILABLE"),
            "recorded_options": {"newman": ["usps"], "GLOBAL": {"level": "info"}},
        }

        time.sleep(0.2)  # Let report thread loop do some work
        assert state._sent_initial_report is True

        client = cast(FakeBuildsenseClient, state._client)
        assert len(client.run_start_calls) == 1
        assert len(client.workunits_calls) == 1
        assert len(client.run_end_calls) == 0
        pants_context.mark_ended()
        reporter(completed_workunits=[], started_workunits=[], context=pants_context, finished=True)  # type: ignore[arg-type]
        assert reporter._call_count == 2
        end_report = state._end_report_data
        assert end_report is not None
        assert len(end_report) == 2
        final_run_tracker, call_count = end_report
        assert call_count == 1
        assert final_run_tracker.has_ended is True
        assert final_run_tracker.log_file is not None
        assert final_run_tracker.log_file.name == "roundtine.log"
        assert len(final_run_tracker.build_stats.pop("workunits")) == 228
        assert final_run_tracker.build_stats == _work_units_fmt_stats(self.get_expected_run_info(with_git, "SUCCESS"))

        assert len(state._client.run_start_calls) == 1
        assert len(state._client.workunits_calls) == 1
        assert len(state._client.run_end_calls) == 1
        assert len(state._client.upload_artifact_calls) == 1

    def test_fast_run(self, with_git: bool, tmp_path: Path, pants_context: FakeWorkunitContext, org_name: str) -> None:
        workunits = load_local_fixture("work_units_fmt")
        pants_context.mark_ended()
        reporter = self._get_reporter(tmp_path, repo_name="ovaltine", org_name=org_name, with_git=with_git)
        assert reporter._call_count == 0
        reporter(completed_workunits=workunits, started_workunits=[], context=pants_context, finished=True)  # type: ignore[arg-type]
        assert reporter._call_count == 1
        assert reporter._enabled is True
        state = reporter._build_state
        assert state._run_id == "no-soup-for-you-come-back-one-year"
        assert state._initial_report is None
        end_report = state._end_report_data
        assert end_report is not None
        assert len(end_report) == 2
        assert state._sent_initial_report is False
        client = cast(FakeBuildsenseClient, state._client)
        assert len(client.run_start_calls) == 0
        assert len(client.workunits_calls) == 0
        assert len(client.run_end_calls) == 1
        assert len(client.upload_artifact_calls) == 1

        final_run_tracker, call_count = end_report
        assert call_count == 0
        assert final_run_tracker.has_ended is True
        assert final_run_tracker.log_file is not None
        assert final_run_tracker.log_file.name == "roundtine.log"
        assert len(final_run_tracker.build_stats.pop("workunits")) == 228
        assert final_run_tracker.build_stats == _work_units_fmt_stats(self.get_expected_run_info(with_git, "SUCCESS"))

    def test_run_no_log(
        self, with_git: bool, tmp_path: Path, pants_context: FakeWorkunitContext, org_name: str
    ) -> None:
        workunits = load_local_fixture("work_units_fmt")
        pants_context.mark_ended(disable_log=True)
        reporter = self._get_reporter(tmp_path, repo_name="ovaltine", org_name=org_name, with_git=with_git)
        assert reporter._call_count == 0
        reporter(completed_workunits=workunits, started_workunits=[], context=pants_context, finished=True)  # type: ignore[arg-type]
        assert reporter._call_count == 1
        assert reporter._enabled is True
        state = reporter._build_state
        assert state._run_id == "no-soup-for-you-come-back-one-year"
        assert state._initial_report is None
        end_report = state._end_report_data
        assert end_report is not None
        assert len(end_report) == 2
        assert state._sent_initial_report is False
        client = cast(FakeBuildsenseClient, state._client)
        assert len(client.run_start_calls) == 0
        assert len(client.workunits_calls) == 0
        assert len(client.run_end_calls) == 1
        assert len(client.upload_artifact_calls) == 0

        final_run_tracker, call_count = end_report
        assert call_count == 0
        assert final_run_tracker.has_ended is True
        assert final_run_tracker.log_file is None
        assert len(final_run_tracker.build_stats.pop("workunits")) == 228
        assert final_run_tracker.build_stats == _work_units_fmt_stats(self.get_expected_run_info(with_git, "SUCCESS"))

    def test_global_metrics(
        self, with_git: bool, tmp_path: Path, caplog, pants_context: FakeWorkunitContext, org_name: str
    ) -> None:
        workunits = load_local_fixture("work_units_fmt")
        pants_context.mark_ended()
        reporter = self._get_reporter(tmp_path, repo_name="ovaltine", org_name=org_name, with_git=with_git)
        reporter(completed_workunits=workunits, started_workunits=[], context=pants_context, finished=True)  # type: ignore[arg-type]
        end_report = reporter._build_state._end_report_data
        assert end_report is not None
        final_run_tracker, call_count = end_report
        assert final_run_tracker.build_stats["counters"] == {
            "metric_one": 1,
        }

    def test_new_histogram_version(
        self, with_git: bool, tmp_path: Path, caplog, pants_context: FakeWorkunitContext, org_name: str
    ) -> None:
        workunits = load_local_fixture("work_units_fmt")
        pants_context.mark_ended()
        pants_context.set_histogram_version(2)
        reporter = self._get_reporter(tmp_path, repo_name="ovaltine", org_name=org_name, with_git=with_git)
        assert reporter._call_count == 0
        reporter(completed_workunits=workunits, started_workunits=[], context=pants_context, finished=True)  # type: ignore[arg-type]
        assert reporter._call_count == 1
        assert reporter._enabled is True
        state = reporter._build_state
        assert state._run_id == "no-soup-for-you-come-back-one-year"
        assert state._initial_report is None
        end_report = state._end_report_data
        assert end_report is not None
        final_run_tracker, call_count = end_report
        assert call_count == 0
        assert final_run_tracker.has_ended is True
        assert final_run_tracker.log_file is not None
        assert final_run_tracker.log_file.name == "roundtine.log"
        assert len(final_run_tracker.build_stats.pop("workunits")) == 228
        assert_messages(caplog, "Cannot encode internal metrics histograms: unexpected version 2")

        assert final_run_tracker.build_stats == _work_units_fmt_stats(
            self.get_expected_run_info(with_git, "SUCCESS"), with_histograms=False
        )

    def test_empty_histograms(
        self, with_git: bool, tmp_path: Path, pants_context: FakeWorkunitContext, org_name: str
    ) -> None:
        workunits = load_local_fixture("work_units_fmt")
        pants_context.clear_histograms()
        pants_context.mark_ended()
        reporter = self._get_reporter(tmp_path, repo_name="ovaltine", org_name=org_name, with_git=with_git)
        assert reporter._call_count == 0
        reporter(completed_workunits=workunits, started_workunits=[], context=pants_context, finished=True)  # type: ignore[arg-type]
        end_report = reporter._build_state._end_report_data
        assert end_report is not None
        final_run_tracker, call_count = end_report
        assert len(final_run_tracker.build_stats.pop("workunits")) == 228

        assert final_run_tracker.build_stats == _work_units_fmt_stats(
            self.get_expected_run_info(with_git, "SUCCESS"), with_histograms=False
        )

    def test_handle_work_units_under_circle_ci(self, with_git: bool, tmp_path: Path, org_name: str) -> None:
        reporter = self._get_reporter(
            tmp_path,
            ci_env_pattern=None,
            env=load_fixture("circleci_pull_request_env"),
            repo_name="ovaltine",
            org_name=org_name,
            with_git=with_git,
        )
        reporter(
            completed_workunits=[], started_workunits=[], context=FakeWorkunitContext.create(tmp_path), finished=False  # type: ignore[arg-type]
        )
        assert reporter._enabled is True
        assert reporter._build_state is not None
        report = reporter._build_state._initial_report
        assert report is not None
        assert report.has_ended is False
        ci_env = report.build_stats["ci_env"]
        assert len(ci_env) == 29
        assert ci_env["CIRCLE_BUILD_URL"] == "https://circleci.com/gh/toolchainlabs/toolchain/22462"
        assert ci_env["CIRCLE_PROJECT_REPONAME"] == "toolchain"

    def test_handle_work_units_under_github_actions(self, with_git: bool, tmp_path: Path, org_name: str) -> None:
        env = load_fixture("github_actions_tag_env")
        env.update({"SOME_VALUE": "jerry", "OTHER": "FESTIVUS"})
        reporter = self._get_reporter(
            tmp_path,
            ci_env_pattern=None,
            env=env,
            repo_name="ovaltine",
            org_name=org_name,
            with_git=with_git,
        )
        reporter(
            completed_workunits=[], started_workunits=[], context=FakeWorkunitContext.create(tmp_path), finished=False  # type: ignore[arg-type]
        )
        assert reporter._enabled is True
        assert reporter._build_state is not None
        report = reporter._build_state._initial_report
        assert report is not None
        assert report.has_ended is False
        ci_env = report.build_stats["ci_env"]
        assert len(ci_env) == 24
        assert ci_env["GITHUB_REPOSITORY"] == "toolchainlabs/toolchain"
        assert ci_env["GITHUB_SHA"] == "da75f05cadb42d8e1a06655f021fab86c5857f4d"
        assert {"SOME_VALUE", "OTHER"}.intersection(ci_env.keys()) == set()

    def test_handle_work_units_under_github_actions_with_secrets(
        self, with_git: bool, tmp_path: Path, org_name: str
    ) -> None:
        env = load_fixture("github_actions_pr_env")
        env.update(
            {
                "JERRY": "jambalaya",
                "GITHUB_TOKEN": "festivus",
                "GITHUB_SECRET": "fears-of-strength",
                "OTHER_SECRET": "bob",
                "GITHUB_ACCESS_KEY": "mole",
                "GITHUB_SECRET_ID": "soup",
                "GITHUB_TOKEN_ID": "berg",
            }
        )
        reporter = self._get_reporter(
            tmp_path,
            ci_env_pattern=None,
            env=env,
            repo_name="ovaltine",
            org_name=org_name,
            with_git=with_git,
        )
        reporter(
            completed_workunits=[], started_workunits=[], context=FakeWorkunitContext.create(tmp_path), finished=False  # type: ignore[arg-type]
        )
        assert reporter._enabled is True
        assert reporter._build_state is not None
        report = reporter._build_state._initial_report
        assert report is not None
        assert report.has_ended is False
        ci_env = report.build_stats["ci_env"]
        assert len(ci_env) == 24
        assert ci_env["GITHUB_REPOSITORY_OWNER"] == "toolchainlabs"
        assert ci_env["GITHUB_REF"] == "refs/pull/7011/merge"
        assert {
            "GITHUB_TOKEN",
            "GITHUB_SECRET",
            "JERRY",
            "OTHER_SECRET",
            "GITHUB_ACCESS_KEY",
            "GITHUB_SECRET_ID",
            "GITHUB_TOKEN_ID",
        }.intersection(ci_env.keys()) == set()

    def test_start_and_finished_with_platform_Data(
        self, with_git: bool, tmp_path: Path, pants_context: FakeWorkunitContext, org_name: str
    ) -> None:
        workunits = load_local_fixture("work_units_fmt")
        reporter = self._get_reporter(
            tmp_path, repo_name="ovaltine", org_name=org_name, collect_platform_data=True, with_git=with_git
        )
        assert reporter._call_count == 0
        reporter(completed_workunits=workunits, started_workunits=[], context=pants_context, finished=False)  # type: ignore[arg-type]
        assert reporter._call_count == 1
        assert reporter._enabled is True
        state = reporter._build_state
        assert state._end_report_data is None
        assert state._run_id == "no-soup-for-you-come-back-one-year"
        initial_report = state._initial_report
        assert initial_report is not None
        assert initial_report.has_ended is False
        assert initial_report.log_file is None
        assert initial_report.build_stats == {
            "run_info": self.get_expected_run_info(with_git, "NOT_AVAILABLE"),
            "recorded_options": {"newman": ["usps"], "GLOBAL": {"level": "info"}},
        }

        time.sleep(0.2)  # Let report thread loop do some work
        assert state._sent_initial_report is True

        client = cast(FakeBuildsenseClient, state._client)
        assert len(client.run_start_calls) == 1
        assert len(client.workunits_calls) == 1
        assert len(client.run_end_calls) == 0
        pants_context.mark_ended()
        reporter(completed_workunits=[], started_workunits=[], context=pants_context, finished=True)  # type: ignore[arg-type]
        assert reporter._call_count == 2
        end_report = state._end_report_data
        assert end_report is not None
        assert len(end_report) == 2
        final_run_tracker, call_count = end_report
        assert call_count == 1
        assert final_run_tracker.has_ended is True
        assert final_run_tracker.log_file is not None
        assert final_run_tracker.log_file.name == "roundtine.log"
        assert len(final_run_tracker.build_stats.pop("workunits")) == 228
        build_stats = final_run_tracker.build_stats
        platform_info = build_stats.pop("platform")
        assert set(platform_info.keys()) == {
            "os",
            "os_release",
            "processor",
            "python_version",
            "python_implementation",
            "architecture",
            "cpu_count",
            "mem_bytes",
        }
        # Conservative assertions here to avoid breaking this test
        assert platform_info["python_version"].startswith("3.")
        assert platform_info["python_implementation"] == "CPython"
        assert build_stats == _work_units_fmt_stats(self.get_expected_run_info(with_git, "SUCCESS"))

        assert len(state._client.run_start_calls) == 1
        assert len(state._client.workunits_calls) == 1
        assert len(state._client.run_end_calls) == 1
        assert len(state._client.upload_artifact_calls) == 1
