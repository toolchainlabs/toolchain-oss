# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from itertools import chain
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element, tostring

from defusedxml import ElementTree

from toolchain.buildsense.ingestion.run_processors.common import (
    BaseHandler,
    ExtractedArtifacts,
    FileInfo,
    WorkUnitWithArtifacts,
)
from toolchain.buildsense.ingestion.run_processors.console import ConsoleArtifactsHandler

_logger = logging.getLogger(__name__)


@dataclass
class PytestSuiteData:
    target: str
    xml_data: Element
    stdout: str | None
    stderr: str | None


class PytestJUnitXmlArtifactsHandler(BaseHandler):
    _CONTENT_TYPE = "pytest_results/v2"
    _NAME = "pytest_results"
    _ARTIFACT_TYPE = "xml_results"

    def __init__(self) -> None:
        self._tests_data: list[PytestSuiteData] = []
        self._file_info: FileInfo | None = None
        self._significant_work_unit_ids: list[str] = []
        self._pytest_work_unit_ids: set[str] = set()
        self._test_suite_outcome = "SUCCESS"
        self._console_artifact_types = frozenset(ConsoleArtifactsHandler.types)
        self._converter = PytestResultsProcessor()

    def handle_work_unit_artifacts(self, artifacts_wu: WorkUnitWithArtifacts, goal: str) -> bool:
        if self._ARTIFACT_TYPE not in artifacts_wu.artifacts:
            return bool(
                self._console_artifact_types.intersection(artifacts_wu.artifacts)
                and artifacts_wu.significant_work_unit_id in self._pytest_work_unit_ids
            )
        artifact = artifacts_wu.artifacts[self._ARTIFACT_TYPE]
        artifact_work_unit = artifacts_wu.work_unit
        target_addr = artifact_work_unit.get("metadata", {}).get("address")
        artifacts = artifact_work_unit["artifacts"]
        stdout = artifacts.get("stdout")
        stderr = artifacts.get("stderr")
        for xml_path, xml_str in artifact.items():
            xml_data = ElementTree.fromstring(xml_str)
            if not self.is_pytest(xml_data):
                return False
            self._tests_data.append(
                PytestSuiteData(
                    target=target_addr or self._get_test_file_path(xml_path),
                    xml_data=xml_data,
                    stdout=stdout,
                    stderr=stderr,
                )
            )
        self._significant_work_unit_ids.append(artifacts_wu.significant_work_unit_id)
        self._pytest_work_unit_ids.add(artifacts_wu.workunit_id)
        return True

    def is_pytest(self, xml_data: Element) -> bool:
        return bool(len(xml_data) and "pytest" in xml_data[0].get("name", "").lower())  # type: ignore[union-attr]

    def _get_files(self) -> list[FileInfo]:
        if not self._tests_data:
            return []
        test_runs = self._converter.convert_pytest_junit_xmls(self._tests_data)
        self._test_suite_outcome = self._converter.get_outcome(test_runs)

        artifacts = [
            {
                "name": "Test Results",
                "content_type": self._CONTENT_TYPE,
                "content": {
                    "test_runs": test_runs,
                },
            }
        ]
        self._file_info = FileInfo.create_json_file(self._NAME, artifacts)
        return [self._file_info]

    def _get_artifacts_dict(self) -> dict[str, list[dict]]:
        file_info = self._file_info
        if not file_info:
            return {}
        if len(self._significant_work_unit_ids) > 1:
            # This is no big deal since the work_unit_id in the artifacts_dict is not particularly important.
            # But I want to log this so I can see when it happens, add tests and adapt the code to properly deal with it.
            _logger.info(f"multiple_significant_work_unit_ids: {self._significant_work_unit_ids}")
        return {
            "test": [
                {
                    "work_unit_id": self._significant_work_unit_ids[-1],
                    "name": self._NAME,
                    "description": "Test results",
                    "artifacts": file_info.name,
                    "content_types": [self._CONTENT_TYPE],
                    "priority": 1,
                    "result": self._test_suite_outcome,
                }
            ]
        }

    def get_artifacts(self) -> ExtractedArtifacts:
        return ExtractedArtifacts(files=self._get_files(), work_units_by_goal=self._get_artifacts_dict())

    def _get_test_file_path(self, xml_path: str) -> str:
        # TODO(gshuflin) - we should modify pants to pass this path up directly, rather than calculating it from the XML filename.
        # This sort of parsing is fragile.
        xml_filename = Path(xml_path).parts[-1]

        # We expect XML filenames to look like `path.to.python.file.py.test_target_name.xml`
        test_file_path_components = xml_filename.split(".")[:-2]
        if test_file_path_components[-1] == "py":
            test_file_path_components.pop()
            test_file = test_file_path_components.pop()
            test_file_path_components.append(f"{test_file}.py")

        return Path(*test_file_path_components).as_posix()


class PytestResultsProcessor:
    # for sorting purposes
    _DEFAULT_OUTCOME_SCORE = 50
    _TEST_OUTCOME_PRIORITY = {
        "pass": 10,
        "xfail": 20,
        "skip": 50,
        "fail": 100,
    }

    def __init__(self) -> None:
        self._unknown_outcomes: set[str] = set()

    @property
    def unknown_outcomes(self) -> list[str]:
        return sorted(self._unknown_outcomes)

    def get_outcome(self, pytest_results: list[dict]) -> str:
        for pytest_run in pytest_results:
            for suite in pytest_run["tests"]:
                for test in suite["tests"]:
                    if test["outcome"] == "fail":
                        return "FAILURE"
        return "SUCCESS"

    def _get_score(self, outcome: str) -> int:
        outcome_score = self._TEST_OUTCOME_PRIORITY.get(outcome)
        if outcome_score is not None:
            return outcome_score
        self._unknown_outcomes.add(outcome)
        return self._DEFAULT_OUTCOME_SCORE

    def _get_test_suite_priority(self, test_suite: dict) -> int:
        score = 0
        for tests_group in test_suite["tests"]:
            for test in tests_group["tests"]:
                score = max(score, self._get_score(test["outcome"]))
        return score

    def convert_pytest_junit_xmls(self, xml_tests_data: Sequence[PytestSuiteData]) -> list[dict]:
        test_suites = (_convert_pytest_junit_xml(test_data) for test_data in xml_tests_data)
        return sorted(test_suites, key=self._get_test_suite_priority, reverse=True)

    def _convert_pytest_junit_xml(self, test_data: PytestSuiteData) -> dict:
        test_suite_data = list(
            chain(*(_test_suite_to_dict(test_data.target, test_suite_xml) for test_suite_xml in test_data.xml_data))
        )
        return {
            "tests": test_suite_data,
            "timing": {
                "total": _total_time(test_suite_data),
            },
            "target": test_data.target,
            "outputs": {"stdout": test_data.stdout, "stderr": test_data.stderr},
        }


def _convert_pytest_junit_xml(test_data: PytestSuiteData) -> dict:
    test_suite_data = list(
        chain(*(_test_suite_to_dict(test_data.target, test_suite_xml) for test_suite_xml in test_data.xml_data))
    )
    return {
        "tests": test_suite_data,
        "timing": {
            "total": _total_time(test_suite_data),
        },
        "target": test_data.target,
        "outputs": {"stdout": test_data.stdout, "stderr": test_data.stderr},
    }


def _test_suite_to_dict(test_file_path: str, test_suite_xml: Element) -> list[dict]:
    # currently grouping by class name (or file name for test function)
    # TODO: group by tests w/ different parameters (i.e. usage of pytest.mark.parametrize)
    test_groups = defaultdict(list)
    for test_case_xml in test_suite_xml:
        if test_case_xml.tag != "testcase":
            continue
        test_case, group = _test_case_to_dict(test_case_xml)
        test_groups[group].append(test_case)
    return [
        {
            "name": name or test_file_path,
            "test_file_path": test_file_path,
            "time": _total_time(tests),
            "tests": tests,
        }
        for name, tests in test_groups.items()
    ]


def _total_time(tests: list[dict]) -> float:
    total_time = Decimal(sum(test["time"] for test in tests))
    return float(total_time.quantize(Decimal("1.00")))


def _test_case_to_dict(test_case_xml: Element) -> tuple[dict[str, Any], str | None]:
    test_case: dict[str, Any] = {}
    if not test_case_xml:
        outcome = "pass"
    else:
        children = tuple(test_case_xml)
        tags = {child.tag for child in children}
        if tags == {"skipped"}:
            if len(children) != 1:
                raw_xml = tostring(test_case_xml).decode()
                _logger.warning(f"test_case_to_dict unexpected_children: {raw_xml}")
            child_attrs = children[0].attrib
            skip_type = child_attrs.get("type") or child_attrs.get("message") or ""
            if skip_type.startswith("pytest."):
                *_, outcome = skip_type.partition(".")
            else:
                outcome = "skip"
            test_case["results"] = [_results_to_dict(child) for child in children]
        elif tags == {"failure"}:
            outcome = "fail"
            test_case["results"] = [_results_to_dict(child) for child in children]
        elif tags == {"error"}:
            outcome = "error"
            test_case["results"] = [_results_to_dict(child) for child in children]
        else:
            raw_xml = tostring(test_case_xml).decode()
            _logger.warning(f"test_case_to_dict tags_unexpected {raw_xml}")
            outcome = "unknown"
    test_case.update(test_case_xml.attrib)  # type: ignore[arg-type]
    if "name" not in test_case or "classname" not in test_case:
        outcome = "error"
    group = test_case.pop("classname", "UNKNOWN")
    name = test_case.get("name", "UNKNOWN")
    test_case["time"] = float(test_case["time"])
    if "[" in name:
        # parameterized test, add another grouping level.
        index = name.index("[")
        group = f"{group}.{name[:index]}"
        test_case["name"] = name[index + 1 : -1]
    test_case["outcome"] = outcome
    return test_case, group


def _results_to_dict(result_xml: Element) -> dict[str, Any]:
    result: dict[str, str] = {"message": result_xml.attrib["message"]}
    if result_xml.text:
        result["text"] = result_xml.text
    return result
