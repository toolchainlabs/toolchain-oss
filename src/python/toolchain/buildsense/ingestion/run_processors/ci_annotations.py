# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.buildsense.ingestion.run_info_raw_store import RunInfoRawStore
from toolchain.buildsense.records.run_info import RunInfo

_logger = logging.getLogger(__name__)


_ANNOTATABLE_GOALS = frozenset(("lint",))


_FLAKE8_PARSER = re.compile(
    r"(?P<file_path>[\w\d\\/.]+):(?P<line>\d+):(?P<column>\d+): (?P<error_code>[A-Z]+\d+) (?P<msg>.+)"
)


@dataclass(frozen=True)
class SourceErrorAnnotation:
    file_path: str
    lines: tuple[int, int]
    columns: tuple[int, int]
    error_code: str
    message: str


def flake8_errors_parser(context: str, raw_errors: list[str]) -> list[SourceErrorAnnotation]:
    parse_failed_lines: list[str] = []
    errors: list[SourceErrorAnnotation] = []
    for flak8e_error in raw_errors:
        match = _FLAKE8_PARSER.match(flak8e_error)
        if not match:
            parse_failed_lines.append(flak8e_error)
        else:
            groups_dict = match.groupdict()
            line = int(groups_dict["line"])
            column = int(groups_dict["column"])
            errors.append(
                SourceErrorAnnotation(
                    file_path=groups_dict["file_path"],
                    lines=(line, line),
                    columns=(column, column),
                    error_code=groups_dict["error_code"],
                    message=groups_dict["msg"],
                )
            )
    if parse_failed_lines:
        _logger.warning(f"Failed to parse {len(parse_failed_lines)} for {context}: {parse_failed_lines[:5]}")
    return errors


class CIAnnotationHelper:
    _ERRORS_PARSERS_MAP = {
        "flake8": flake8_errors_parser,
    }

    def get_annotations(self, run_info: RunInfo) -> list[SourceErrorAnnotation]:
        error_payloads = self._get_error_payloads(run_info)
        annotations = []
        for rule_name, raw_errors in error_payloads.items():
            parser_func = self._get_parser_func(rule_name)
            if not parser_func:
                raise ToolchainAssertion(f"Failed to get parser func for {rule_name}")
            annotations.extend(parser_func(run_info.run_id, raw_errors))
        return annotations

    def _get_error_payloads(self, run_info: RunInfo) -> dict[str, list[str]]:
        raw_store = RunInfoRawStore.for_run_info(run_info)
        work_units_file = raw_store.get_work_units_artifacts(run_info)
        if not work_units_file:
            raise ToolchainAssertion(f"Can't load work units artifacts file for run_id={run_info.run_id}")
        wu_artifacts = json.loads(work_units_file.content)
        error_payloads: dict[str, list[str]] = defaultdict(list)
        for goal in _ANNOTATABLE_GOALS:
            for artifact_dict in wu_artifacts.get(goal, []):
                rule_name = artifact_dict["name"]
                if not self._get_parser_func(rule_name):
                    continue
                artifact_file = raw_store.get_named_data(run_info=run_info, name=artifact_dict["artifacts"])
                if not artifact_file:
                    raise ToolchainAssertion(
                        f"Failed to load artifact: {artifact_dict['artifacts']} for {run_info.run_id}"
                    )
                for artifact_data in json.loads(artifact_file.content):
                    # TODO: check content_type
                    error_payloads[rule_name].append(artifact_data["content"])
        return error_payloads

    def _get_parser_func(self, rule_name: str) -> Callable[[str, list[str]], list[SourceErrorAnnotation]] | None:
        for tool, parse_func in self._ERRORS_PARSERS_MAP.items():
            if tool in rule_name:
                return parse_func
        return None
