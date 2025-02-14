# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.buildsense.ingestion.run_processors.python_coverage_xml import get_files_coverage, process_xml_coverage
from toolchain.buildsense.test_utils.fixtures_loader import load_xml_fixture


def test_get_files_coverage() -> None:
    xml_str = load_xml_fixture("pytest_coverage")
    result = get_files_coverage(xml_str)
    assert len(result) == 28


def test_process_xml_coverage() -> None:
    xml_str = load_xml_fixture("pytest_coverage")
    coverate_stats = process_xml_coverage(xml_str)
    assert coverate_stats.lines_covered == 747
    assert coverate_stats.lines_uncovered == 155
