# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from xml.etree.ElementTree import Element, fromstring

import pytest

from toolchain.buildsense.ingestion.run_processors.pytest_junit_xml import PytestResultsProcessor, PytestSuiteData
from toolchain.buildsense.test_utils.fixtures_loader import load_fixture, load_xml_fixture


def load_xml(fixture: str) -> Element:
    return fromstring(load_xml_fixture(fixture))


@pytest.mark.parametrize(
    ("fixture"),
    [
        "test_classes_fail",
        "test_classes_success",
        "tests_functions_success",
        "test_clases_xfail",
        "test_errors",
        "test_errors_pytest_crash",
        "test_results_with_properties",
        "tests_skipped",
    ],
)
def test_convert_pytest_junit_xmls(fixture) -> None:
    xml_doc = load_xml(fixture)
    tsd = PytestSuiteData(
        target=f"{fixture}.py",
        xml_data=xml_doc,
        stdout="He stopped short?",
        stderr="Three squares? You can’t spare three squares?",
    )
    processor = PytestResultsProcessor()
    # import json
    # res = processor.convert_pytest_junit_xmls([tsd])
    # fn = f"src/python/toolchain/buildsense/test_utils/fixtures/{fixture}.json"
    # open(fn, "w").write(json.dumps(res, indent=4))
    exprect_json_data = load_fixture(fixture)
    assert processor.convert_pytest_junit_xmls([tsd]) == exprect_json_data


def test_chain_tests() -> None:
    processor = PytestResultsProcessor()
    json_test_data = processor.convert_pytest_junit_xmls(
        [
            PytestSuiteData(
                target="somedir/test_file.py",
                xml_data=load_xml("test_classes_success"),
                stdout="You have the chicken, the hen, and the rooster",
                stderr="Jerry, just remember, it’s not a lie if you believe it.",
            ),
            PytestSuiteData(
                target="somedir/test_file.py",
                xml_data=load_xml("tests_functions_success"),
                stdout="Moles — freckles’ ugly cousin",
                stderr="Human, it’s human to be moved by a fragrance.",
            ),
        ]
    )
    # import json
    # fn = "src/python/toolchain/buildsense/test_utils/fixtures/chained_pytest_results.json"
    # open(fn, "w").write(json.dumps(json_test_data, indent=4))
    assert json_test_data == load_fixture("chained_pytest_results")
