# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import zlib
from collections.abc import Iterable
from enum import Enum, unique

import pytest

from toolchain.buildsense.ingestion.run_processors.artifacts import GoalArtifactsExtractor
from toolchain.buildsense.ingestion.run_processors.common import FileInfo, StandaloneArtifact
from toolchain.buildsense.test_utils.data_parser import create_run_info
from toolchain.buildsense.test_utils.fixtures_loader import load_bytes_fixture, load_fixture
from toolchain.util.test.util import assert_messages


@unique
class ParentIDMode(Enum):
    SINGLE_ONLY = "single"
    MULTIPLE_ONLY = "multiple"
    BOTH = "both"


def assert_pants_options(files: tuple[FileInfo, ...], options_file_index: int = 0, extra_files: int = 0) -> dict:
    assert len(files) == 2 + extra_files
    artifacts_descriptor = files[-1]
    assert artifacts_descriptor.compressed is False
    assert artifacts_descriptor.name == "artifacts_work_units.json"
    assert artifacts_descriptor.content_type == "application/json"
    content = json.loads(artifacts_descriptor.content)
    assert "pants_options" in content
    assert content["pants_options"] == [
        {
            "name": "pants_options",
            "description": "Pants Options",
            "artifacts": "pants_options.json",
            "content_types": ["pants_options"],
        }
    ]
    options_file = files[options_file_index]
    assert options_file.compressed is False
    assert options_file.name == "pants_options.json"
    assert options_file.content_type == "application/json"
    options_content = json.loads(options_file.content)
    options = options_content[0].pop("content")
    assert options_content == [{"name": "Options", "content_type": "pants_options"}]
    assert isinstance(options, dict)
    assert "GLOBAL" in options
    return options


def load_fixture_with_parent_ids(name: str, use_parent_ids_mode: ParentIDMode) -> dict:
    build_stats = load_fixture(fixture_name=name)
    for wu in build_stats.get("workunits", []):
        if "parent_ids" in wu and use_parent_ids_mode == ParentIDMode.MULTIPLE_ONLY:
            continue
        # for now all of our fixtures have single only, so we only need to handle that
        # As we add newer fixture this logic will need to evolve.
        assert (
            "parent_ids" not in wu
        ), "load_fixture_with_parent_ids must add support for multiple parent IDs in fixtures"
        parent_id = wu.get("parent_id")
        if not parent_id:
            continue
        if use_parent_ids_mode in {ParentIDMode.BOTH, ParentIDMode.MULTIPLE_ONLY}:
            wu["parent_ids"] = [parent_id]
            if use_parent_ids_mode == ParentIDMode.MULTIPLE_ONLY:
                del wu["parent_id"]
    return build_stats


class TestGoalArtifactsExtractor:
    @pytest.fixture(params=ParentIDMode)
    def parent_id_mode(self, request) -> ParentIDMode:
        return request.param

    @pytest.fixture()
    def extractor(self) -> GoalArtifactsExtractor:
        return GoalArtifactsExtractor.create()

    def _to_json(self, file_info: FileInfo) -> dict | list:
        assert file_info.content_type == "application/json"
        content = file_info.content
        if file_info.compressed:
            content = zlib.decompress(content)
        return json.loads(content)

    def _names(self, file_infos: Iterable[FileInfo]) -> list[str]:
        return [fi.name for fi in file_infos]

    def _assert_compressed(self, file_infos: Iterable[FileInfo], *compressed: str) -> None:
        for fi in file_infos:
            if fi.name in compressed:
                assert fi.compressed is True
                assert zlib.decompress(fi.content)
            else:
                assert fi.compressed is False

    def test_extract_fmt_stderr_artifacts(
        self, extractor: GoalArtifactsExtractor, parent_id_mode: ParentIDMode
    ) -> None:
        build_stats = load_fixture_with_parent_ids("black_fmt_with_artifacts", parent_id_mode)
        run_info = create_run_info(build_stats, "3")
        result = extractor.get_artifacts(run_info, build_stats, None)
        assert result.has_metrics is False
        files = result.files
        assert self._names(files) == [
            "fmt_84ecd738a862391f_artifacts.json",
            "pants_options.json",
            "artifacts_work_units.json",
        ]
        self._assert_compressed(files)
        assert self._to_json(files[-1]) == {
            "pants_options": [
                {
                    "artifacts": "pants_options.json",
                    "description": "Pants Options",
                    "name": "pants_options",
                    "content_types": ["pants_options"],
                },
            ],
            "fmt": [
                {
                    "work_unit_id": "36be844a11cbad03",
                    "name": "pants.backend.python.lint.black.rules.black_fmt",
                    "description": "Format using Black",
                    "artifacts": "fmt_84ecd738a862391f_artifacts.json",
                    "content_types": ["text/plain"],
                }
            ],
        }
        assert self._to_json(files[0]) == [
            {
                "name": "stderr",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 9026, "start_time": 80},
                "content": "All done! ✨ 🍰 ✨\n34 files left unchanged.\n",
            }
        ]

    def test_extract_lint_with_find_binary_rules_in_tree(
        self, extractor: GoalArtifactsExtractor, parent_id_mode: ParentIDMode
    ) -> None:
        build_stats = load_fixture_with_parent_ids("ci_branch_final_lint", parent_id_mode)
        run_info = create_run_info(build_stats, "3")
        result = extractor.get_artifacts(run_info, build_stats, None)
        assert result.has_metrics is False
        files = result.files
        assert self._names(files) == [
            "lint_e9cd6edf2d6d156a_artifacts.json",
            "pants_options.json",
            "artifacts_work_units.json",
        ]
        self._assert_compressed(files)
        assert self._to_json(files[-1]) == {
            "pants_options": [
                {
                    "artifacts": "pants_options.json",
                    "description": "Pants Options",
                    "name": "pants_options",
                    "content_types": ["pants_options"],
                },
            ],
            "lint": [
                {
                    "work_unit_id": "0f0d0477c6f54606",
                    "name": "pants.backend.python.lint.pylint.rules.pylint_lint",
                    "description": "Lint using Pylint",
                    "artifacts": "lint_e9cd6edf2d6d156a_artifacts.json",
                    "content_types": ["text/plain"],
                }
            ],
        }
        assert self._to_json(files[0]) == [
            {
                "name": "stdout",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 369161, "start_time": 17938},
                "content": "\n------------------------------------\nYour code has been rated at 10.00/10\n\n",
            }
        ]

    def test_extract_lint_artifacts_significant_without_desc(
        self, extractor: GoalArtifactsExtractor, parent_id_mode: ParentIDMode
    ) -> None:
        build_stats = load_fixture_with_parent_ids("lint_significant_parent_no_desc", parent_id_mode)
        run_info = create_run_info(build_stats, "3")
        result = extractor.get_artifacts(run_info, build_stats, None)
        assert result.has_metrics is False
        files = result.files
        assert self._names(files) == [
            "lint_7fde3dd7079531eb_artifacts.json",
            "lint_e44bcee80b8d1a04_artifacts.json",
            "lint_846f9282a20552c3_artifacts.json",
            "pants_options.json",
            "artifacts_work_units.json",
        ]
        self._assert_compressed(files)
        assert self._to_json(files[-1]) == {
            "pants_options": [
                {
                    "artifacts": "pants_options.json",
                    "description": "Pants Options",
                    "name": "pants_options",
                    "content_types": ["pants_options"],
                },
            ],
            "lint": [
                {
                    "work_unit_id": "25a035749a92f7a1",
                    "name": "pants.backend.python.lint.bandit.rules.bandit_lint",
                    "description": "Lint using Bandit",
                    "artifacts": "lint_846f9282a20552c3_artifacts.json",
                    "content_types": ["text/plain"],
                },
                {
                    "work_unit_id": "8dad3c0c7fa73f24",
                    "name": "pants.backend.python.lint.black.rules.black_lint",
                    "description": "Lint using Black",
                    "artifacts": "lint_7fde3dd7079531eb_artifacts.json",
                    "content_types": ["text/plain"],
                },
                {
                    "work_unit_id": "6c63f16f81427d9d",
                    "name": "pants.backend.python.lint.pylint.rules.pylint_lint",
                    "description": "Lint using Pylint",
                    "artifacts": "lint_e44bcee80b8d1a04_artifacts.json",
                    "content_types": ["text/plain"],
                },
            ],
        }

        assert self._to_json(files[0]) == [
            {
                "name": "stderr",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 9986, "start_time": 16819},
                "content": "All done! ✨ 🍰 ✨\n31 files would be left unchanged.\n",
            }
        ]
        assert self._to_json(files[1]) == [
            {
                "name": "stdout",
                "timing_msec": {"run_time": 15346, "start_time": 36448},
                "content_type": "text/plain",
                "content": "\n--------------------------------------------------------------------\nYour code has been rated at 10.00/10 (previous run: 10.00/10, +0.00)\n\n",
            }
        ]
        assert self._to_json(files[2]) == [
            {
                "name": "stdout",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 1705, "start_time": 8814},
                "content": "Run started:2020-08-10 16:20:03.847376\n\nTest results:\n\tNo issues identified.\n\nCode scanned:\n\tTotal lines of code: 1065\n\tTotal lines skipped (#nosec): 0\n\nRun metrics:\n\tTotal issues (by severity):\n\t\tUndefined: 0.0\n\t\tLow: 0.0\n\t\tMedium: 0.0\n\t\tHigh: 0.0\n\tTotal issues (by confidence):\n\t\tUndefined: 0.0\n\t\tLow: 0.0\n\t\tMedium: 0.0\n\t\tHigh: 0.0\nFiles skipped (0):\n",
            },
            {
                "name": "stderr",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 1705, "start_time": 8814},
                "content": "[main]\tINFO\tprofile include tests: None\n[main]\tINFO\tprofile exclude tests: B603,B607,B314,B404,B322,B303,B405\n[main]\tINFO\tcli include tests: None\n[main]\tINFO\tcli exclude tests: None\n[main]\tINFO\tusing config: build-support/python/bandit.yaml\n[main]\tINFO\trunning on Python 3.8.5\n",
            },
        ]

    def test_extract_no_artifacts(self, extractor: GoalArtifactsExtractor, parent_id_mode: ParentIDMode) -> None:
        build_stats = load_fixture_with_parent_ids("ci_build_pr_final_2", parent_id_mode)
        del build_stats["recorded_options"]
        run_info = create_run_info(build_stats, "2")
        result = extractor.get_artifacts(run_info, build_stats, None)
        assert result.has_metrics is False
        files = result.files
        assert len(files) == 0

    def test_extract_options_only(self, extractor: GoalArtifactsExtractor, parent_id_mode: ParentIDMode) -> None:
        build_stats = load_fixture_with_parent_ids("ci_build_pr_final_2", parent_id_mode)
        run_info = create_run_info(build_stats, "2")
        result = extractor.get_artifacts(run_info, build_stats, None)
        assert result.has_metrics is False
        files = result.files
        assert_pants_options(files)

    def test_extract_lint_aliased_goals(self, extractor: GoalArtifactsExtractor, parent_id_mode: ParentIDMode) -> None:
        build_stats = load_fixture_with_parent_ids("ci_lint_aliased_goals", parent_id_mode)
        run_info = create_run_info(build_stats, "3")
        result = extractor.get_artifacts(run_info, build_stats, None)
        assert result.has_metrics is False
        files = result.files
        assert self._names(files) == [
            "lint_d46dc478746a22c2_artifacts.json",
            "pants_options.json",
            "artifacts_work_units.json",
        ]
        self._assert_compressed(files)
        assert self._to_json(files[-1]) == {
            "pants_options": [
                {
                    "artifacts": "pants_options.json",
                    "description": "Pants Options",
                    "name": "pants_options",
                    "content_types": ["pants_options"],
                },
            ],
            "lint": [
                {
                    "work_unit_id": "7026f706e18ab4a5",
                    "name": "pants.backend.python.lint.bandit.rules.bandit_lint",
                    "description": "Lint with Bandit",
                    "artifacts": "lint_d46dc478746a22c2_artifacts.json",
                    "content_types": ["text/plain"],
                }
            ],
        }

    def test_extract_pytest_junit_xml_artifacts(
        self, extractor: GoalArtifactsExtractor, parent_id_mode: ParentIDMode
    ) -> None:
        build_stats = load_fixture_with_parent_ids("run_with_pytest_xml_results", parent_id_mode)
        run_info = create_run_info(build_stats, "3")
        result = extractor.get_artifacts(run_info, build_stats, None)
        assert result.has_metrics is False
        files = result.files
        assert self._names(files) == [
            "pytest_results.json",
            "test_4b44bcd6813e75cb_artifacts.json",
            "pants_options.json",
            "artifacts_work_units.json",
        ]
        self._assert_compressed(files)
        assert self._to_json(files[-1]) == {
            "pants_options": [
                {
                    "artifacts": "pants_options.json",
                    "description": "Pants Options",
                    "name": "pants_options",
                    "content_types": ["pants_options"],
                },
            ],
            "test": [
                {
                    "work_unit_id": "6077393d5f2e7d81",
                    "name": "pytest_results",
                    "description": "Test results",
                    "artifacts": "pytest_results.json",
                    "content_types": ["pytest_results/v2"],
                    "result": "SUCCESS",
                },
                {
                    "work_unit_id": "330b79f44dc69fdb",
                    "name": "pants.backend.python.goals.pytest_runner.run_python_test",
                    "description": "Run Pytest",
                    "artifacts": "test_4b44bcd6813e75cb_artifacts.json",
                    "content_types": ["text/plain"],
                },
            ],
        }
        assert self._to_json(files[0]) == [
            {
                "name": "Test Results",
                "content_type": "pytest_results/v2",
                "content": {
                    "test_runs": [
                        {
                            "tests": [
                                {
                                    "name": "src.python.toolchain.aws.s3_test.test_s3_url_functionality",
                                    "test_file_path": "src/python/toolchain/aws/s3_test.py",
                                    "time": 1.35,
                                    "tests": [
                                        {
                                            "name": "dummy/path-s3://testbucket/dummy/path-http://testbucket.s3.amazonaws.com/dummy/path",
                                            "time": 1.194,
                                            "outcome": "pass",
                                        },
                                        {
                                            "name": "dummy/path/-s3://testbucket/dummy/path/-http://testbucket.s3.amazonaws.com/dummy/path/",
                                            "time": 0.077,
                                            "outcome": "pass",
                                        },
                                        {
                                            "name": "/dummy/path-s3://testbucket//dummy/path-http://testbucket.s3.amazonaws.com//dummy/path",
                                            "time": 0.08,
                                            "outcome": "pass",
                                        },
                                    ],
                                },
                                {
                                    "name": "src.python.toolchain.aws.s3_test.test_parse_s3_url_failure",
                                    "test_file_path": "src/python/toolchain/aws/s3_test.py",
                                    "time": 0.16,
                                    "tests": [
                                        {"name": "http://foo.com/bar/baz", "time": 0.079, "outcome": "pass"},
                                        {"name": "s4://blah/blah/blah/", "time": 0.082, "outcome": "pass"},
                                    ],
                                },
                                {
                                    "name": "src.python.toolchain.aws.s3_test",
                                    "test_file_path": "src/python/toolchain/aws/s3_test.py",
                                    "time": 1.28,
                                    "tests": [
                                        {"name": "test_exists_and_delete", "time": 0.157, "outcome": "pass"},
                                        {"name": "test_keys_with_prefix", "time": 0.108, "outcome": "pass"},
                                        {"name": "test_upload_json_str", "time": 0.192, "outcome": "pass"},
                                        {"name": "test_reading_and_writing_content", "time": 0.078, "outcome": "pass"},
                                        {"name": "test_get_content_or_none", "time": 0.092, "outcome": "pass"},
                                        {"name": "test_upload_file", "time": 0.091, "outcome": "pass"},
                                        {"name": "test_download_file", "time": 0.111, "outcome": "pass"},
                                        {"name": "test_copy_object", "time": 0.123, "outcome": "pass"},
                                        {"name": "test_upload_directory", "time": 0.085, "outcome": "pass"},
                                        {"name": "test_download_directory", "time": 0.24, "outcome": "pass"},
                                    ],
                                },
                            ],
                            "timing": {"total": 2.79},
                            "target": "src/python/toolchain/aws/s3_test.py",
                            "outputs": {"stdout": None, "stderr": None},
                        }
                    ]
                },
            }
        ]

    def test_extract_fail_to_find_goal(self, caplog, extractor: GoalArtifactsExtractor) -> None:
        # There is an issue here when running with all ParentIDMode.BOTH - causes some kind of stack overflow I need to debug
        # So skipping this use case for now.
        build_stats = load_fixture_with_parent_ids("run_with_pytest_xml_results", ParentIDMode.SINGLE_ONLY)
        run_info = create_run_info(build_stats, "3")
        run_info.computed_goals = ["lint"]  # confuse extracttor so it can't find goal
        result = extractor.get_artifacts(run_info, build_stats, None)
        assert result.has_metrics is False
        files = result.files
        assert result.has_metrics is False
        assert_pants_options(files)
        record = assert_messages(caplog, r"Can't find goal work unit for")
        assert record is not None
        assert record.levelname == "WARNING"
        assert (
            "attempted='pants.core.goals.test.enrich_test_result,pants.core.goals.test.run_tests,select'"
            in record.message
        )

    def test_extract_find_interpreter_error(
        self, extractor: GoalArtifactsExtractor, parent_id_mode: ParentIDMode
    ) -> None:
        build_stats = load_fixture_with_parent_ids("run_with_pex_failure", parent_id_mode)
        run_info = create_run_info(build_stats, "3")
        result = extractor.get_artifacts(run_info, build_stats, None)
        assert result.has_metrics is False
        files = result.files
        assert self._names(files) == [
            "fmt_803f7f68f2694df4_artifacts.json",
            "pants_options.json",
            "artifacts_work_units.json",
        ]
        self._assert_compressed(files)
        assert self._to_json(files[-1]) == {
            "pants_options": [
                {
                    "artifacts": "pants_options.json",
                    "description": "Pants Options",
                    "name": "pants_options",
                    "content_types": ["pants_options"],
                },
            ],
            "fmt": [
                {
                    "work_unit_id": "43e42f0ab52d6e97",
                    "name": "pants.backend.python.lint.black.rules.setup_black",
                    "description": "setup_black",
                    "artifacts": "fmt_803f7f68f2694df4_artifacts.json",
                    "content_types": ["text/plain"],
                }
            ],
        }

    def test_extract_typecheck(self, extractor: GoalArtifactsExtractor, parent_id_mode: ParentIDMode) -> None:
        build_stats = load_fixture_with_parent_ids("run_mypy_typecheck", parent_id_mode)
        run_info = create_run_info(build_stats, "3")
        result = extractor.get_artifacts(run_info, build_stats, None)
        assert result.has_metrics is False
        files = result.files
        self._assert_compressed(files)
        assert self._names(files) == [
            "typecheck_6c308575213b0b11_artifacts.json",
            "typecheck_23844fa0ae3dba76_artifacts.json",
            "typecheck_b806aa5548d38a28_artifacts.json",
            "pants_options.json",
            "artifacts_work_units.json",
        ]
        assert self._to_json(files[-1]) == {
            "pants_options": [
                {
                    "artifacts": "pants_options.json",
                    "description": "Pants Options",
                    "name": "pants_options",
                    "content_types": ["pants_options"],
                },
            ],
            "typecheck": [
                {
                    "work_unit_id": "32c88ef5fe5296f4",
                    "name": "pants.backend.python.typecheck.mypy.rules.mypy_typecheck",
                    "description": "Typecheck using MyPy",
                    "artifacts": "typecheck_6c308575213b0b11_artifacts.json",
                    "content_types": ["text/plain"],
                },
                {
                    "work_unit_id": "32c88ef5fe5296f4",
                    "name": "pants.backend.python.typecheck.mypy.rules.mypy_typecheck",
                    "description": "Typecheck using MyPy",
                    "artifacts": "typecheck_23844fa0ae3dba76_artifacts.json",
                    "content_types": ["text/plain"],
                },
                {
                    "work_unit_id": "32c88ef5fe5296f4",
                    "name": "pants.backend.python.typecheck.mypy.rules.mypy_typecheck",
                    "description": "Typecheck using MyPy",
                    "artifacts": "typecheck_b806aa5548d38a28_artifacts.json",
                    "content_types": ["text/plain"],
                },
            ],
        }
        assert self._to_json(files[0]) == [
            {
                "name": "stdout",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 19215, "start_time": 140818},
                "content": "Success: no issues found in 20 source files\n",
            }
        ]

    def test_extract_count_loc(self, extractor: GoalArtifactsExtractor, parent_id_mode: ParentIDMode) -> None:
        build_stats = load_fixture_with_parent_ids("count_loc_run", parent_id_mode)
        run_info = create_run_info(build_stats, "3")
        result = extractor.get_artifacts(run_info, build_stats, None)
        assert result.has_metrics is False
        files = result.files
        assert self._names(files) == [
            "count-loc_1547c5ded140dbc6_artifacts.json",
            "pants_options.json",
            "artifacts_work_units.json",
        ]
        self._assert_compressed(files)
        assert self._to_json(files[-1]) == {
            "pants_options": [
                {
                    "artifacts": "pants_options.json",
                    "description": "Pants Options",
                    "name": "pants_options",
                    "content_types": ["pants_options"],
                },
            ],
            "count-loc": [
                {
                    "work_unit_id": "668427a04b7baed7",
                    "name": "pants.backend.project_info.count_loc.count_loc",
                    "description": "`count-loc` goal",
                    "artifacts": "count-loc_1547c5ded140dbc6_artifacts.json",
                    "content_types": ["text/plain"],
                },
            ],
        }
        assert self._to_json(files[0]) == [
            {
                "name": "stdout",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 308, "start_time": 5562},
                "content": "───────────────────────────────────────────────────────────────────────────────\nLanguage                 Files     Lines   Blanks  Comments     Code Complexity\n───────────────────────────────────────────────────────────────────────────────\nPython                     952     97007    10237     10614    76156       4720\nTerraform                  201      9027     1176      2086     5765        187\nYAML                       172     19686      509      1934    17243          0\nJSON                        87    178821       14         0   178807          0\nHTML                        84      4002      714        11     3277          0\nPlain Text                  27      1266        9         0     1257          0\nJavaScript                  15      1979      172       442     1365        199\nSVG                          8       218        0         4      214          3\nCSS                          5      1670      314        94     1262          0\nXML                          3       972       57         0      915          0\nJinja                        1        88        8        10       70         22\nMarkdown                     1        31        6         0       25          0\n───────────────────────────────────────────────────────────────────────────────\nTotal                     1556    314767    13216     15195   286356       5131\n───────────────────────────────────────────────────────────────────────────────\nEstimated Cost to Develop $10,264,715\nEstimated Schedule Effort 37.170860 months\nEstimated People Required 32.711388\n───────────────────────────────────────────────────────────────────────────────\n\n",
            }
        ]

    def test_extract_logs_with_typecheck(self, extractor: GoalArtifactsExtractor, parent_id_mode: ParentIDMode) -> None:
        build_stats = load_fixture_with_parent_ids("run_mypy_typecheck", parent_id_mode)
        run_info = create_run_info(build_stats, "3")
        result = extractor.get_artifacts(run_info, build_stats, "pants_run_log.txt")
        assert result.has_metrics is False
        files = result.files
        assert self._names(files) == [
            "typecheck_6c308575213b0b11_artifacts.json",
            "typecheck_23844fa0ae3dba76_artifacts.json",
            "typecheck_b806aa5548d38a28_artifacts.json",
            "pants_options.json",
            "artifacts_work_units.json",
        ]
        self._assert_compressed(files)
        assert self._to_json(files[-1]) == {
            "pants_options": [
                {
                    "artifacts": "pants_options.json",
                    "description": "Pants Options",
                    "name": "pants_options",
                    "content_types": ["pants_options"],
                },
            ],
            "typecheck": [
                {
                    "work_unit_id": "32c88ef5fe5296f4",
                    "name": "pants.backend.python.typecheck.mypy.rules.mypy_typecheck",
                    "description": "Typecheck using MyPy",
                    "artifacts": "typecheck_6c308575213b0b11_artifacts.json",
                    "content_types": ["text/plain"],
                },
                {
                    "work_unit_id": "32c88ef5fe5296f4",
                    "name": "pants.backend.python.typecheck.mypy.rules.mypy_typecheck",
                    "description": "Typecheck using MyPy",
                    "artifacts": "typecheck_23844fa0ae3dba76_artifacts.json",
                    "content_types": ["text/plain"],
                },
                {
                    "work_unit_id": "32c88ef5fe5296f4",
                    "name": "pants.backend.python.typecheck.mypy.rules.mypy_typecheck",
                    "description": "Typecheck using MyPy",
                    "artifacts": "typecheck_b806aa5548d38a28_artifacts.json",
                    "content_types": ["text/plain"],
                },
            ],
            "logs": [
                {
                    "name": "Logs",
                    "description": "Pants run log",
                    "artifacts": "pants_run_log.txt",
                    "content_types": ["text/plain"],
                }
            ],
        }
        assert self._to_json(files[0]) == [
            {
                "name": "stdout",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 19215, "start_time": 140818},
                "content": "Success: no issues found in 20 source files\n",
            }
        ]

    def test_extract_typecheck_with_metrics(
        self, extractor: GoalArtifactsExtractor, parent_id_mode: ParentIDMode
    ) -> None:
        build_stats = load_fixture_with_parent_ids("run_typecheck_with_metrics.legacy_counters", parent_id_mode)
        run_info = create_run_info(build_stats, "3")
        result = extractor.get_artifacts(run_info, build_stats, "pants_run_log.txt")
        assert result.has_metrics is True
        files = result.files
        assert self._names(files) == [
            "typecheck_315b5ba2465d4026_artifacts.json",
            "typecheck_dfa587806fee8f5c_artifacts.json",
            "aggregate_metrics.json",
            "pants_options.json",
            "artifacts_work_units.json",
        ]
        self._assert_compressed(files)
        assert self._to_json(files[-1]) == {
            "pants_options": [
                {
                    "artifacts": "pants_options.json",
                    "description": "Pants Options",
                    "name": "pants_options",
                    "content_types": ["pants_options"],
                },
            ],
            "typecheck": [
                {
                    "work_unit_id": "a5693bb72f1e7735",
                    "name": "pants.backend.python.typecheck.mypy.rules.mypy_typecheck",
                    "description": "Typecheck using MyPy",
                    "artifacts": "typecheck_315b5ba2465d4026_artifacts.json",
                    "result": "SUCCESS",
                    "content_types": ["text/plain"],
                },
                {
                    "work_unit_id": "a5693bb72f1e7735",
                    "name": "pants.backend.python.typecheck.mypy.rules.mypy_typecheck",
                    "description": "Typecheck using MyPy",
                    "artifacts": "typecheck_dfa587806fee8f5c_artifacts.json",
                    "result": "SUCCESS",
                    "content_types": ["text/plain"],
                },
            ],
            "metrics": [
                {
                    "name": "metrics",
                    "description": "Run metrics",
                    "artifacts": "aggregate_metrics.json",
                    "content_types": ["work_unit_metrics"],
                }
            ],
            "logs": [
                {
                    "name": "Logs",
                    "description": "Pants run log",
                    "artifacts": "pants_run_log.txt",
                    "content_types": ["text/plain"],
                }
            ],
        }
        assert self._to_json(files[0]) == [
            {
                "name": "stdout",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 19409, "start_time": 9686},
                "content": "Success: no issues found in 51 source files\n",
            }
        ]
        assert self._to_json(files[1]) == [
            {
                "name": "stdout",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 6805, "start_time": 9926},
                "content": "Success: no issues found in 6 source files\n",
            }
        ]
        assert self._to_json(files[2]) == [
            {"name": "Metrics", "content_type": "work_unit_metrics", "content": {"local_execution_requests": 2}}
        ]

    def test_extract_artifacts_with_failed_lint_goal(
        self, extractor: GoalArtifactsExtractor, parent_id_mode: ParentIDMode
    ) -> None:
        build_stats = load_fixture_with_parent_ids("run_lint_failed", parent_id_mode)
        run_info = create_run_info(build_stats, "3")
        result = extractor.get_artifacts(run_info, build_stats, None)
        assert result.has_metrics is True
        files = result.files
        assert self._names(files) == [
            "lint_b687fcb3e7245dca_artifacts.json",
            "lint_6b10cbb0668a3ada_artifacts.json",
            "lint_03a5453824ac0ce9_artifacts.json",
            "lint_46cda90659828c90_artifacts.json",
            "aggregate_metrics.json",
            "pants_options.json",
            "artifacts_work_units.json",
        ]
        self._assert_compressed(files)
        assert self._to_json(files[-1]) == {
            "pants_options": [
                {
                    "artifacts": "pants_options.json",
                    "description": "Pants Options",
                    "name": "pants_options",
                    "content_types": ["pants_options"],
                },
            ],
            "lint": [
                {
                    "work_unit_id": "14c7c78806e8117e",
                    "name": "pants.backend.python.lint.flake8.rules.flake8_lint",
                    "description": "Lint with Flake8",
                    "artifacts": "lint_03a5453824ac0ce9_artifacts.json",
                    "content_types": ["text/plain"],
                    "result": "FAILURE",
                },
                {
                    "work_unit_id": "b385f9d89258c3f7",
                    "name": "pants.backend.python.lint.pylint.rules.pylint_lint",
                    "description": "Lint using Pylint",
                    "artifacts": "lint_46cda90659828c90_artifacts.json",
                    "content_types": ["text/plain"],
                    "result": "FAILURE",
                },
                {
                    "work_unit_id": "3957c47c811571cc",
                    "name": "pants.backend.python.lint.bandit.rules.bandit_lint",
                    "description": "Lint with Bandit",
                    "artifacts": "lint_6b10cbb0668a3ada_artifacts.json",
                    "content_types": ["text/plain"],
                    "result": "SUCCESS",
                },
                {
                    "work_unit_id": "8ca7cf388b1c4508",
                    "name": "pants.backend.python.lint.black.rules.black_lint",
                    "description": "Lint with Black",
                    "artifacts": "lint_b687fcb3e7245dca_artifacts.json",
                    "content_types": ["text/plain"],
                    "result": "SUCCESS",
                },
            ],
            "metrics": [
                {
                    "name": "metrics",
                    "description": "Run metrics",
                    "artifacts": "aggregate_metrics.json",
                    "content_types": ["work_unit_metrics"],
                }
            ],
        }
        assert self._to_json(files[3]) == [
            {
                "name": "stdout",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 13853, "start_time": 77285},
                "content": "\n------------------------------------\nYour code has been rated at 10.00/10\n\n",
            },
            {
                "name": "stdout",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 22150, "start_time": 77285},
                "content": "************* Module install_buildbarn_storage\nsrc/python/toolchain/prod/installs/install_buildbarn_storage.py:14:0: W0611: Unused dataclass imported from dataclasses (unused-import)\nsrc/python/toolchain/prod/installs/install_buildbarn_storage.py:17:0: W0611: Unused ElasticSearch imported from toolchain.aws.elasticsearch (unused-import)\nsrc/python/toolchain/prod/installs/install_buildbarn_storage.py:20:0: W0611: Unused ToolchainEnv imported from toolchain.constants (unused-import)\nsrc/python/toolchain/prod/installs/install_buildbarn_storage.py:21:0: W0611: Unused ElasticSearchCuratorBuilder imported from toolchain.prod.builders.build_es_curator (unused-import)\n\n-----------------------------------\nYour code has been rated at 9.98/10\n\n",
            },
        ]

    def test_with_coverage_xml(self, extractor: GoalArtifactsExtractor, parent_id_mode: ParentIDMode) -> None:
        build_stats = load_fixture_with_parent_ids("run_test_with_coverage", parent_id_mode)
        standalone = StandaloneArtifact(
            workunit_id="8b186f5d508be631",
            name="coverage_xml_coverage.xml",
            content_type="application/xml",
            content=load_bytes_fixture("pytest_coverage.xml"),
        )
        run_info = create_run_info(build_stats, "3")
        result = extractor.get_artifacts(
            run_info, build_stats, log_artifact_name=None, standalone_artifacts=[standalone]
        )
        assert result.has_metrics is True
        files = result.files
        assert self._names(files) == [
            "test_6108eaaea0ebd806_artifacts.json",
            "coverage_summary.json",
            "aggregate_metrics.json",
            "pants_options.json",
            "artifacts_work_units.json",
        ]
        self._assert_compressed(files)
        assert self._to_json(files[-1]) == {
            "pants_options": [
                {
                    "artifacts": "pants_options.json",
                    "description": "Pants Options",
                    "name": "pants_options",
                    "content_types": ["pants_options"],
                },
            ],
            "test": [
                {
                    "work_unit_id": "4a532c452df67ab8",
                    "name": "pants.backend.python.goals.pytest_runner.run_python_test",
                    "description": "Run Pytest",
                    "artifacts": "test_6108eaaea0ebd806_artifacts.json",
                    "result": "SUCCESS",
                    "content_types": ["text/plain"],
                },
                {
                    "work_unit_id": "8b186f5d508be631",
                    "name": "coverage_summary",
                    "description": "Code Coverage Summary",
                    "artifacts": "coverage_summary.json",
                    "content_types": ["coverage_summary"],
                },
            ],
            "metrics": [
                {
                    "name": "metrics",
                    "description": "Run metrics",
                    "artifacts": "aggregate_metrics.json",
                    "content_types": ["work_unit_metrics"],
                }
            ],
        }
        assert self._to_json(files[0]) == [
            {
                "name": "stdout",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 9856, "start_time": 9798},
                "content": "\x1b[1m============================= test session starts ==============================\x1b[0m\nplatform darwin -- Python 3.8.5, pytest-6.1.2, py-1.9.0, pluggy-0.13.1\nrootdir: /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executionfJGXzP\nplugins: cov-2.10.1, icdiff-0.5, django-4.1.0\ncollected 5 items\n\nsrc/python/toolchain/servicerouter/views_test.py \x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m                   [100%]\x1b[0m\n\n\n\n\x1b[32m============================== \x1b[32m\x1b[1m5 passed\x1b[0m\x1b[32m in 3.38s\x1b[0m\x1b[32m ===============================\x1b[0m\n",
            },
            {
                "name": "stdout",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 11038, "start_time": 9799},
                "content": "\x1b[1m============================= test session starts ==============================\x1b[0m\nplatform darwin -- Python 3.8.5, pytest-6.1.2, py-1.9.0, pluggy-0.13.1\nrootdir: /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executionC34dVV\nplugins: cov-2.10.1, icdiff-0.5, django-4.1.0\ncollected 11 items\n\nsrc/python/toolchain/servicerouter/config_test.py \x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[33m            [100%]\x1b[0m\n\n\x1b[33m=============================== warnings summary ===============================\x1b[0m\nsrc/python/toolchain/servicerouter/config_test.py::TestStaticContentConfig::test_for_prod\n  /Users/asher/.cache/pants/named_caches/pex_root/installed_wheels/83a24cae78f4e371354f9197c4c7a337be93fd41/boto-2.49.0-py2.py3-none-any.whl/boto/plugin.py:40: DeprecationWarning: the imp module is deprecated in favour of importlib; see the module's documentation for alternative uses\n    import imp\n\n-- Docs: https://docs.pytest.org/en/stable/warnings.html\n\n\n\x1b[33m======================== \x1b[32m11 passed\x1b[0m, \x1b[33m\x1b[1m1 warning\x1b[0m\x1b[33m in 4.67s\x1b[0m\x1b[33m =========================\x1b[0m\n",
            },
            {
                "name": "stdout",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 10675, "start_time": 9799},
                "content": "\x1b[1m============================= test session starts ==============================\x1b[0m\nplatform darwin -- Python 3.8.5, pytest-6.1.2, py-1.9.0, pluggy-0.13.1\nrootdir: /private/var/folders/hv/p6g7p3p95d19gtm5cfkrk5w00000gn/T/process-executionmtFVWj\nplugins: cov-2.10.1, icdiff-0.5, django-4.1.0\ncollected 9 items\n\nsrc/python/toolchain/servicerouter/services_router_test.py \x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m     [100%]\x1b[0m\n\n\n\n\x1b[32m============================== \x1b[32m\x1b[1m9 passed\x1b[0m\x1b[32m in 4.21s\x1b[0m\x1b[32m ===============================\x1b[0m\n",
            },
        ]
        assert self._to_json(files[1]) == [
            {
                "name": "Code Coverage Summary",
                "content_type": "coverage_summary",
                "content": {"lines_covered": 747, "lines_uncovered": 155},
            }
        ]

    def test_extract_typecheck_with_local_cache(
        self, extractor: GoalArtifactsExtractor, parent_id_mode: ParentIDMode
    ) -> None:
        build_stats = load_fixture_with_parent_ids("typecheck_with_local_cache", parent_id_mode)
        run_info = create_run_info(build_stats, "3")
        result = extractor.get_artifacts(run_info, build_stats, None)
        assert result.has_metrics is True
        files = result.files
        assert self._names(files) == [
            "typecheck_a4e06f5debbc9d96_artifacts.json",
            "aggregate_metrics.json",
            "pants_options.json",
            "targets_specs.json",
            "artifacts_work_units.json",
        ]
        self._assert_compressed(files)
        assert self._to_json(files[-1]) == {
            "typecheck": [
                {
                    "work_unit_id": "84cf3608de8b9874",
                    "name": "pants.backend.python.typecheck.mypy.rules.mypy_typecheck",
                    "description": "Typecheck using MyPy",
                    "artifacts": "typecheck_a4e06f5debbc9d96_artifacts.json",
                    "content_types": ["text/plain"],
                    "result": "FAILURE",
                },
            ],
            "metrics": [
                {
                    "name": "metrics",
                    "description": "Run metrics",
                    "artifacts": "aggregate_metrics.json",
                    "content_types": ["work_unit_metrics"],
                }
            ],
            "pants_options": [
                {
                    "name": "pants_options",
                    "description": "Pants Options",
                    "artifacts": "pants_options.json",
                    "content_types": ["pants_options"],
                }
            ],
            "targets_specs": [
                {
                    "name": "targets_specs",
                    "description": "Expanded targets specs",
                    "artifacts": "targets_specs.json",
                    "content_types": ["targets_specs"],
                }
            ],
        }

        assert self._to_json(files[0]) == [
            {
                "name": "stdout",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 5978, "start_time": 7487},
                "content": 'src/python/toolchain/aws/iam.py: note: In member "get_users_with_old_keys" of class "IAM":\nsrc/python/toolchain/aws/iam.py:76:41: error: Argument "tags" to "IAMUser" has\nincompatible type "Dict[str, str]"; expected "bool"  [arg-type]\n                        name=username, tags=self.tags_to_dict(tags), key_i...\n                                            ^\nsrc/python/toolchain/aws/iam.py:79:16: error: Incompatible return value type\n(got "List[IAMUser]", expected "List[str]")  [return-value]\n            return users\n                   ^\nFound 2 errors in 1 file (checked 38 source files)\n',
            }
        ]
        counters = self._to_json(files[1])[0]["content"]
        assert set(counters.keys()) == {
            "remote_cache_requests_cached",
            "local_cache_time_saved_ms_90",
            "local_cache_read_errors",
            "local_cache_requests_uncached",
            "remote_cache_write_errors",
            "local_cache_time_saved_ms_std_dev",
            "remote_execution_success",
            "local_cache_time_saved_ms_25",
            "remote_execution_rpc_errors",
            "local_store_read_blob_size_90",
            "local_cache_write_errors",
            "remote_cache_requests_uncached",
            "local_store_read_blob_size_min",
            "remote_execution_rpc_execute",
            "remote_cache_read_errors",
            "local_store_read_blob_size_mean",
            "local_cache_time_saved_ms_75",
            "local_cache_time_saved_ms_50",
            "local_store_read_blob_size_99",
            "remote_execution_errors",
            "remote_execution_timeouts",
            "local_cache_time_saved_ms_mean",
            "local_store_read_blob_size_25",
            "local_store_read_blob_size_50",
            "local_store_read_blob_size_std_dev",
            "local_cache_total_time_saved_ms",
            "remote_cache_write_finished",
            "local_cache_requests_cached",
            "remote_execution_requests",
            "local_execution_requests",
            "local_store_read_blob_size_95",
            "remote_cache_requests",
            "remote_execution_rpc_retries",
            "local_store_read_blob_size_max",
            "local_store_read_blob_size_total_observations",
            "local_store_read_blob_size_sum",
            "local_cache_time_saved_ms_min",
            "remote_cache_total_time_saved_ms",
            "remote_execution_rpc_wait_execution",
            "remote_cache_speculation_remote_completed_first",
            "local_store_read_blob_size_75",
            "local_cache_time_saved_ms_total_observations",
            "local_cache_time_saved_ms_sum",
            "remote_cache_write_started",
            "remote_cache_speculation_local_completed_first",
            "local_cache_time_saved_ms_max",
            "local_cache_requests",
            "local_cache_time_saved_ms_95",
            "local_cache_time_saved_ms_99",
        }

    def test_extract_max_files_reached(
        self, monkeypatch, caplog, extractor: GoalArtifactsExtractor, parent_id_mode: ParentIDMode
    ) -> None:
        monkeypatch.setattr(extractor, "MAX_FILES", 2, raising=True)
        build_stats = load_fixture_with_parent_ids("lint_significant_parent_no_desc", parent_id_mode)
        run_info = create_run_info(build_stats, "3")
        result = extractor.get_artifacts(run_info, build_stats, None)
        assert result.has_metrics is False
        assert self._names(result.files) == ["pants_options.json", "artifacts_work_units.json"]
        record = caplog.records[-1]
        assert record.levelname == "ERROR"
        assert (
            record.message
            == "extract_artifacts has too many files, not storing them. artifacts_files=3 goals=1 extracted for run_id=pants_run_2020_08_10_09_19_53_335_d79beca8755a471caf99664bcb145e34 repo_id=pole"
        )

    def test_process_java_junit_xml(self, extractor: GoalArtifactsExtractor, parent_id_mode: ParentIDMode) -> None:
        build_stats = load_fixture_with_parent_ids("run_with_java_junit_xml_results", parent_id_mode)
        run_info = create_run_info(build_stats, "3")
        result = extractor.get_artifacts(run_info, build_stats, None)
        assert result.has_metrics is True
        files = result.files
        assert self._names(files) == [
            "test_1497f6022cf245a2_artifacts.json",
            "aggregate_metrics.json",
            "pants_options.json",
            "targets_specs.json",
            "artifacts_work_units.json",
        ]
        self._assert_compressed(files)
        assert self._to_json(files[0]) == [
            {
                "name": "stdout",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 7, "start_time": 9},
                "content": "\nThanks for using JUnit! Support its development at https://junit.org/sponsoring\n\n\x1b[36m╷\x1b[0m\n\x1b[36m├─\x1b[0m \x1b[36mJUnit Jupiter\x1b[0m \x1b[32m✔\x1b[0m\n\x1b[36m│  └─\x1b[0m \x1b[36mExampleLibTest\x1b[0m \x1b[32m✔\x1b[0m\n\x1b[36m│     └─\x1b[0m \x1b[34mtestBlah()\x1b[0m \x1b[32m✔\x1b[0m\n\x1b[36m└─\x1b[0m \x1b[36mJUnit Vintage\x1b[0m \x1b[32m✔\x1b[0m\n\nTest run finished after 137 ms\n[         3 containers found      ]\n[         0 containers skipped    ]\n[         3 containers started    ]\n[         0 containers aborted    ]\n[         3 containers successful ]\n[         0 containers failed     ]\n[         1 tests found           ]\n[         0 tests skipped         ]\n[         1 tests started         ]\n[         0 tests aborted         ]\n[         1 tests successful      ]\n[         0 tests failed          ]\n\n",
            },
            {
                "name": "stderr",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 7, "start_time": 9},
                "content": "setrlimit to increase file descriptor limit failed, errno 22\n",
            },
        ]
        assert self._to_json(files[-1]) == {
            "test": [
                {
                    "work_unit_id": "1497f6022cf245a2",
                    "name": "pants.backend.java.test.junit.run_junit_test",
                    "description": "Run JUnit",
                    "artifacts": "test_1497f6022cf245a2_artifacts.json",
                    "content_types": ["text/plain"],
                }
            ],
            "metrics": [
                {
                    "name": "metrics",
                    "description": "Run metrics",
                    "artifacts": "aggregate_metrics.json",
                    "content_types": ["work_unit_metrics"],
                }
            ],
            "pants_options": [
                {
                    "name": "pants_options",
                    "description": "Pants Options",
                    "artifacts": "pants_options.json",
                    "content_types": ["pants_options"],
                }
            ],
            "targets_specs": [
                {
                    "name": "targets_specs",
                    "description": "Expanded targets specs",
                    "artifacts": "targets_specs.json",
                    "content_types": ["targets_specs"],
                }
            ],
        }

    def test_golang_lint(self, extractor: GoalArtifactsExtractor, parent_id_mode: ParentIDMode) -> None:
        build_stats = load_fixture_with_parent_ids("go_lint_pants_runs", parent_id_mode)
        run_info = create_run_info(build_stats, "3")
        result = extractor.get_artifacts(run_info, build_stats, None)
        assert result.has_metrics is True
        files = result.files
        assert self._names(files) == [
            "lint_e34f4a3f727e58a8_artifacts.json",
            "aggregate_metrics.json",
            "pants_options.json",
            "targets_specs.json",
            "platform_info.json",
            "artifacts_work_units.json",
        ]
        self._assert_compressed(files)
        assert self._to_json(files[0]) == [
            {
                "name": "stdout",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 170, "start_time": 2858},
                "env_name": "Local",
                "from_cache": False,
                "content": "src/go/src/toolchain/remoting/pkg/tools.go\n",
            }
        ]
        assert self._to_json(files[-1]) == {
            "lint": [
                {
                    "work_unit_id": "194767a1464a7bee",
                    "name": "pants.backend.go.lint.gofmt.rules.gofmt_lint",
                    "description": "Lint with gofmt",
                    "artifacts": "lint_e34f4a3f727e58a8_artifacts.json",
                    "content_types": ["text/plain"],
                    "result": "SUCCESS",
                }
            ],
            "metrics": [
                {
                    "name": "metrics",
                    "description": "Run metrics",
                    "artifacts": "aggregate_metrics.json",
                    "content_types": ["work_unit_metrics"],
                }
            ],
            "pants_options": [
                {
                    "name": "pants_options",
                    "description": "Pants Options",
                    "artifacts": "pants_options.json",
                    "content_types": ["pants_options"],
                }
            ],
            "targets_specs": [
                {
                    "name": "targets_specs",
                    "description": "Expanded targets specs",
                    "artifacts": "targets_specs.json",
                    "content_types": ["targets_specs"],
                }
            ],
        }

    def test_jvm_run(self, extractor: GoalArtifactsExtractor) -> None:
        build_stats = load_fixture_with_parent_ids("pants_jvm_rules_run", ParentIDMode.MULTIPLE_ONLY)
        run_info = create_run_info(build_stats, "3")
        result = extractor.get_artifacts(run_info, build_stats, None)
        assert result.has_metrics is True
        files = result.files
        assert self._names(files) == [
            "fmt_48fe334f01bc0d59_artifacts.json",
            "package_e48f28b3487e889f_artifacts.json",
            "check_8b4084297bd74c7d_artifacts.json",
            "check_6c7012e1409fe048_artifacts.json",
            "aggregate_metrics.json",
            "pants_options.json",
            "targets_specs.json",
            "artifacts_work_units.json",
        ]

        assert self._to_json(files[0]) == [  # black
            {
                "name": "stderr",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 3, "start_time": 4425},
                "env_name": "Local",
                "from_cache": True,
                "content": "All done! ✨ 🍰 ✨\n56 files left unchanged.\n",
            },
            {
                "name": "stderr",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 10, "start_time": 4425},
                "env_name": "Local",
                "from_cache": True,
                "content": "All done! ✨ 🍰 ✨\n283 files left unchanged.\n",
            },
            {
                "name": "stderr",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 8, "start_time": 4427},
                "env_name": "Local",
                "from_cache": True,
                "content": "All done! ✨ 🍰 ✨\n328 files left unchanged.\n",
            },
            {
                "name": "stderr",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 18, "start_time": 4427},
                "env_name": "Local",
                "from_cache": True,
                "content": "All done! ✨ 🍰 ✨\n329 files left unchanged.\n",
            },
        ]
        assert self._to_json(files[1]) == [
            {
                "name": "stdout",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 0, "start_time": 10126},
                "env_name": "Local",
                "from_cache": True,
                "content": "running bdist_wheel\nrunning build\nrunning build_py\ncreating build\ncreating build/lib.linux",
            },
            {
                "name": "stderr",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 0, "start_time": 10126},
                "env_name": "Local",
                "from_cache": True,
                "content": "package init file 'pants/__init__.py' not found (or not a regular file)\npackage init file ",
            },
            {
                "name": "stdout",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 0, "start_time": 10126},
                "env_name": "Local",
                "from_cache": True,
                "content": "running bdist_wheel\nrunning build\nrunning build_py\ncreating build\ncreating build/lib\ncreat",
            },
            {
                "name": "stderr",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 0, "start_time": 10126},
                "env_name": "Local",
                "from_cache": True,
                "content": "warning: sdist: standard file not found: should have one of README, README.rst, README.txt, README.md\n\nwarning: check: missing meta-data: either (author and author_email) or (maintainer and maintainer_email) must be supplied\n\n",
            },
        ]
        assert self._to_json(files[2]) == [  # javac
            {
                "name": "stdout",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 0, "start_time": 18440},
                "env_name": "Local",
                "from_cache": True,
                "content": "  adding: org/ (stored 0%)\n  adding: org/pantsbuild/ (stored 0%)\n  adding: org/pantsbuild/",
            }
        ]
        assert self._to_json(files[3]) == [  # mypy
            {
                "name": "stdout",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 0, "start_time": 20029},
                "env_name": "Local",
                "from_cache": True,
                "content": "Success: no issues found in 996 source files\n",
            }
        ]

    def test_package_goal(self, extractor: GoalArtifactsExtractor) -> None:
        build_stats = load_fixture_with_parent_ids("pants_package_run", ParentIDMode.MULTIPLE_ONLY)
        run_info = create_run_info(build_stats, "3")
        result = extractor.get_artifacts(run_info, build_stats, None)
        assert result.has_metrics is True
        files = result.files
        assert self._names(files) == [
            "package_ba6b1f442c7a4eed_artifacts.json",
            "aggregate_metrics.json",
            "pants_options.json",
            "targets_specs.json",
            "platform_info.json",
            "artifacts_work_units.json",
        ]
        assert self._to_json(files[0]) == [
            {
                "name": "stdout",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 1226, "start_time": 5400},
                "env_name": "Local",
                "from_cache": False,
                "content": "running bdist_wheel\nrunning build\nrunning build_py\ncreating build\ncreating build/lib\ncreat",
            },
            {
                "name": "stderr",
                "content_type": "text/plain",
                "timing_msec": {"run_time": 1226, "start_time": 5400},
                "env_name": "Local",
                "from_cache": False,
                "content": "package init file 'toolchain/base/__init__.py' not found (or not a regular file)\npackage i",
            },
        ]
        assert self._to_json(files[-1]) == {
            "package": [
                {
                    "work_unit_id": "381eead53210a8c9",
                    "name": "pants.core.goals.package.package_asset",
                    "description": "`package` goal",
                    "artifacts": "package_ba6b1f442c7a4eed_artifacts.json",
                    "content_types": ["text/plain"],
                    "result": "SUCCESS",
                }
            ],
            "metrics": [
                {
                    "name": "metrics",
                    "description": "Run metrics",
                    "artifacts": "aggregate_metrics.json",
                    "content_types": ["work_unit_metrics"],
                }
            ],
            "pants_options": [
                {
                    "name": "pants_options",
                    "description": "Pants Options",
                    "artifacts": "pants_options.json",
                    "content_types": ["pants_options"],
                }
            ],
            "targets_specs": [
                {
                    "name": "targets_specs",
                    "description": "Expanded targets specs",
                    "artifacts": "targets_specs.json",
                    "content_types": ["targets_specs"],
                }
            ],
        }

    def test_mypy_with_local_env_name(self, extractor: GoalArtifactsExtractor) -> None:
        build_stats = load_fixture_with_parent_ids("pants_run_mypy_with_wu_local_env", ParentIDMode.MULTIPLE_ONLY)
        run_info = create_run_info(build_stats, "3")
        result = extractor.get_artifacts(run_info, build_stats, None)
        assert result.has_metrics is True
        files = result.files
        assert self._names(files) == [
            "check_36ac945483c7386a_artifacts.json",
            "aggregate_metrics.json",
            "pants_options.json",
            "targets_specs.json",
            "platform_info.json",
            "artifacts_work_units.json",
        ]
        assert self._to_json(files[0]) == [
            {
                "name": "stdout",
                "content_type": "text/plain",
                "content": "\x1b[1m\x1b[32mSuccess: no issues found in 86 source files\x1b[0;10m\n",
                "timing_msec": {"start_time": 20102, "run_time": 2801},
                "env_name": "Local",
                "from_cache": False,
            }
        ]
        assert self._to_json(files[-1]) == {
            "check": [
                {
                    "work_unit_id": "2162816faf9d5f78",
                    "name": "pants.backend.python.typecheck.mypy.rules.mypy_typecheck",
                    "description": "Typecheck using MyPy - mypy",
                    "artifacts": "check_36ac945483c7386a_artifacts.json",
                    "content_types": ["text/plain"],
                    "result": "SUCCESS",
                }
            ],
            "metrics": [
                {
                    "name": "metrics",
                    "description": "Run metrics",
                    "artifacts": "aggregate_metrics.json",
                    "content_types": ["work_unit_metrics"],
                }
            ],
            "pants_options": [
                {
                    "name": "pants_options",
                    "description": "Pants Options",
                    "artifacts": "pants_options.json",
                    "content_types": ["pants_options"],
                }
            ],
            "targets_specs": [
                {
                    "name": "targets_specs",
                    "description": "Expanded targets specs",
                    "artifacts": "targets_specs.json",
                    "content_types": ["targets_specs"],
                }
            ],
        }
