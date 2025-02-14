# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass

from defusedxml import ElementTree

from toolchain.buildsense.ingestion.run_processors.common import (
    BaseHandler,
    ExtractedArtifacts,
    FileInfo,
    WorkUnitWithArtifacts,
)

_logger = logging.getLogger(__name__)


class XmlCoverageArtifactsHandler(BaseHandler):
    _CONTENT_TYPE = "coverage_summary"
    STANDALONE_NAME = "coverage_xml_coverage.xml"
    types = (STANDALONE_NAME,)

    def __init__(self) -> None:
        self._coverage_xml: str | None = None
        self._file_info: FileInfo | None = None
        self._wu_id: str | None = None

    @property
    def standalone_name(self) -> str:  # type: ignore[override]
        return self.STANDALONE_NAME

    def handle_work_unit_artifacts(self, artifacts_wu: WorkUnitWithArtifacts, goal: str) -> bool:
        handle_count = 0
        for name, artifact in artifacts_wu.artifacts.items():
            handled = self.handle_artifact(
                goal=goal,
                significant_work_unit=artifacts_wu.significant_work_unit,
                artifact_work_unit=artifacts_wu.work_unit,
                name=name,
                artifact=artifact,
            )
            if handled:
                handle_count += 1

        return handle_count > 0

    def handle_artifact(
        self, goal: str, significant_work_unit: dict, artifact_work_unit: dict, name: str, artifact: bytes
    ) -> bool:
        if name not in self.types:
            return False
        self._coverage_xml = artifact.decode()
        self._wu_id = significant_work_unit["workunit_id"]
        return True

    def _get_files(self) -> list[FileInfo]:
        if not self._coverage_xml:
            return []
        coverage_summary = process_xml_coverage(self._coverage_xml)
        artifacts = [
            {
                "name": "Code Coverage Summary",
                "content_type": self._CONTENT_TYPE,
                "content": asdict(coverage_summary),
            }
        ]
        self._file_info = FileInfo.create_json_file("coverage_summary", artifacts)
        return [self._file_info]

    def _get_wu(self) -> dict[str, list[dict]]:
        file_info = self._file_info
        if not file_info:
            return {}
        return {
            "test": [
                {
                    "work_unit_id": self._wu_id,
                    "name": "coverage_summary",
                    "description": "Code Coverage Summary",
                    "artifacts": file_info.name,
                    "content_types": [self._CONTENT_TYPE],
                    "priority": 99,
                }
            ]
        }

    def get_artifacts(self) -> ExtractedArtifacts:
        return ExtractedArtifacts(files=self._get_files(), work_units_by_goal=self._get_wu())


@dataclass(frozen=True)
class FileCoverage:
    filename: str
    data: str
    lines_covered: int
    lines_uncovered: int


@dataclass(frozen=True)
class CoverageStats:
    lines_covered: int
    lines_uncovered: int


def process_xml_coverage(xml_coverage_data: str) -> CoverageStats:
    results = get_files_coverage(xml_coverage_data)
    return aggregate_results(results)


def aggregate_results(results: list[FileCoverage]) -> CoverageStats:
    lines_covered = sum(fc.lines_covered for fc in results)
    lines_uncovered = sum(fc.lines_uncovered for fc in results)
    return CoverageStats(lines_covered=lines_covered, lines_uncovered=lines_uncovered)


def get_files_coverage(xml_coverage_data: str) -> list[FileCoverage]:
    coverage_data = ElementTree.fromstring(xml_coverage_data)
    results = []
    for node in coverage_data.iter("class"):
        filename = node.get("filename")
        if not filename:
            _logger.warning(f"Unable to determine filename for {node=}")
            continue

        file_coverage = []
        for lineset in node.iter("lines"):
            lineno = 0
            for line in lineset.iter("line"):
                number = int(line.get("number"))
                hits = int(line.get("hits"))
                if lineno < number - 1:
                    for _ in range(lineno, number - 1):
                        file_coverage.append("N")
                if hits > 0:
                    file_coverage.append("C")
                else:
                    file_coverage.append("U")
                lineno = number
        results.append(get_result(filename, file_coverage))
    return results


def get_result(filename: str, file_coverage: list[str]) -> FileCoverage:
    data = "".join(file_coverage)
    lines_covered = 0
    lines_uncovered = 0
    for code in data:
        if code == "C":
            lines_covered += 1
        elif code == "U":
            lines_uncovered += 1
    return FileCoverage(filename=filename, data=data, lines_covered=lines_covered, lines_uncovered=lines_uncovered)
