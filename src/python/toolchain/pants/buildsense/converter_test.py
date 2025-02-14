# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import pkg_resources
import pytest
from defusedxml import ElementTree
from pants.engine.fs import Digest, DigestContents, FileContent

from toolchain.base.hashutil import compute_sha256_hexdigest
from toolchain.pants.buildsense.converter import WorkUnitConverter


@dataclass(frozen=True)
class FakeSnapshot:
    digest: Digest
    files: tuple[str, ...]
    dirs: tuple[str, ...]


def load_local_fixture(fixture_name: str):
    return json.loads(pkg_resources.resource_string(__name__, f"fixtures/{fixture_name}.json"))


class FakePantsContext:
    def __init__(self) -> None:
        self._digest_data: dict[str, bytes] = {}
        self._snapshot_data: dict[str, DigestContents] = {}

    def load_work_unit_fixture(self, fixture: str, level_override: str | None = None) -> dict:
        work_units = {}
        for wu_json in load_local_fixture(fixture):
            if level_override:
                wu_json["level"] = level_override
            artifacts = wu_json.get("artifacts")
            if artifacts:
                wu_json["artifacts"] = self._add_artifacts(artifacts)
            work_units[wu_json["span_id"]] = wu_json
        return work_units

    def _add_artifacts(self, artifacts) -> dict[str, Digest]:
        artifacts_links = {}
        for key, value in artifacts.items():
            if isinstance(value, str):
                artifacts_links[f"{key}_digest"] = self.add_digest(value)
            elif isinstance(value, dict):
                artifacts_links[key] = self.add_snapshot(value)
        return artifacts_links

    def add_snapshot(self, snapshot_dict: dict[str, str]) -> FakeSnapshot:
        bytes_keys: list[str] = snapshot_dict.pop("_bytes_keys", [])  # type: ignore[assignment]
        all_data = "".join(snapshot_dict.values()).encode()
        fingerprint = compute_sha256_hexdigest(all_data)
        if fingerprint in self._snapshot_data:
            raise AssertionError(f"Duplicate snapshot for: {snapshot_dict}")
        file_contents = []
        for path, value in snapshot_dict.items():
            content = value.encode()
            if path in bytes_keys:
                content = base64.decodebytes(content)
            file_contents.append(FileContent(path=path, content=content))
        self._snapshot_data[fingerprint] = DigestContents(file_contents)
        digest = Digest(fingerprint=fingerprint, serialized_bytes_length=len(all_data))
        return FakeSnapshot(digest=digest, files=tuple(snapshot_dict.keys()), dirs=tuple())

    def add_digest(self, data: str):
        binary_data = data.encode()
        fingerprint = compute_sha256_hexdigest(binary_data)
        digest = Digest(fingerprint=fingerprint, serialized_bytes_length=len(binary_data))
        if data:
            if fingerprint in self._digest_data:
                raise AssertionError(f"Duplicate digest for: {data}")
            self._digest_data[fingerprint] = binary_data
        return digest

    def single_file_digests_to_bytes(self, digests: Sequence[Digest]) -> list[bytes]:
        return [self._digest_data[digest.fingerprint] for digest in digests]

    def snapshots_to_file_contents(self, snapshots: Sequence[FakeSnapshot]) -> list[DigestContents]:
        return [self._snapshot_data[snapshot.digest.fingerprint] for snapshot in snapshots]


class TestConverter:
    @pytest.fixture()
    def converter(self) -> WorkUnitConverter:
        return WorkUnitConverter.create_local(snapshot_type=FakeSnapshot)

    def test_get_all_work_units_with_digest_artifact(self, converter: WorkUnitConverter) -> None:
        context = FakePantsContext()
        converter.set_context(context)
        fixture_data = context.load_work_unit_fixture("pytest_run")
        assert len(fixture_data) == 1067  # sanity check
        transformed = converter.transform(fixture_data, 3, 44000)
        assert len(transformed) == 15
        all_work_units = converter.get_all_work_units(88, 111111)
        assert len(all_work_units) == 1067
        all_work_units_map = {wu["workunit_id"]: wu for wu in all_work_units}
        process_run_wu = all_work_units_map["0fcf553ae707e055"]
        assert set(process_run_wu["artifacts"].keys()) == {"stdout"}

    def test_get_all_work_units_with_snapshot_and_digest_artifact(self, converter: WorkUnitConverter) -> None:
        context = FakePantsContext()
        converter.set_context(context)
        fixture_data = context.load_work_unit_fixture("work_units_with_xml_results")
        assert len(fixture_data) == 64  # sanity check
        transformed = converter.transform(fixture_data, 3, 44000)
        assert len(transformed) == 62
        all_work_units = converter.get_all_work_units(88, 111111)
        assert converter.get_standalone_artifacts() is None
        assert len(all_work_units) == 64
        all_work_units_map = {wu["workunit_id"]: wu for wu in all_work_units}
        process_run_wu = all_work_units_map["9de6e0cbf2689084"]
        assert set(process_run_wu["artifacts"].keys()) == {"stdout", "stderr"}
        test_results_wu = all_work_units_map["fbfa20fe398ea316"]
        assert test_results_wu["name"] == "pants.core.goals.test.enrich_test_result"
        assert test_results_wu["artifacts"] == {
            "xml_results": {
                "dist/src.python.toolchain.aws.secretsmanager_test.py.tests.xml": '<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest" errors="0" failures="0" skipped="0" tests="9" time="0.083" timestamp="2020-10-02T13:17:03.805271" hostname="Ashers-MacBook-Pro.local"><testcase classname="src.python.toolchain.aws.secretsmanager_test" name="test_secret_name_invalid[%foo]" time="0.004" /><testcase classname="src.python.toolchain.aws.secretsmanager_test" name="test_secret_name_invalid[foo*]" time="0.003" /><testcase classname="src.python.toolchain.aws.secretsmanager_test" name="test_secret_name_invalid[foo-012345]" time="0.003" /><testcase classname="src.python.toolchain.aws.secretsmanager_test" name="test_secret_name_invalid[XXX]" time="0.002" /><testcase classname="src.python.toolchain.aws.secretsmanager_test" name="test_secret_name_valid[foo]" time="0.002" /><testcase classname="src.python.toolchain.aws.secretsmanager_test" name="test_secret_name_valid[@Foo.BAR1+2/4]" time="0.002" /><testcase classname="src.python.toolchain.aws.secretsmanager_test" name="test_secret_name_valid[foo-01234]" time="0.003" /><testcase classname="src.python.toolchain.aws.secretsmanager_test" name="test_secret_name_valid[foo-0123456]" time="0.003" /><testcase classname="src.python.toolchain.aws.secretsmanager_test" name="test_secret_name_valid[XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX]" time="0.004" /></testsuite></testsuites>'
            }
        }

    def test_capture_coverage_data(self, tmp_path: Path, converter: WorkUnitConverter) -> None:
        context = FakePantsContext()
        converter.set_context(context)
        fixture_data = context.load_work_unit_fixture("pytest_with_coverage_xml")
        assert len(fixture_data) == 8  # sanity check
        transformed = converter.transform(fixture_data, 3, 44000)
        assert len(transformed) == 8
        all_work_units = converter.get_all_work_units(88, 111111)
        assert len(all_work_units) == 8
        wu_with_artifacts = [wu for wu in all_work_units if wu.get("artifacts")]
        assert len(wu_with_artifacts) == 1
        artifacts = converter.get_standalone_artifacts()
        assert artifacts is not None
        descriptors = json.loads(artifacts.pop("descriptors.json"))
        assert len(artifacts) == len(descriptors) == 1
        fn = list(artifacts.keys())[0]
        assert descriptors[fn] == {"workunit_id": "c87d0fa47a708e99", "name": "coverage_xml", "path": "coverage.xml"}
        coverage_xml = ElementTree.fromstring(artifacts[fn])
        assert coverage_xml.tag == "coverage"
        assert coverage_xml.attrib == {
            "branch-rate": "0",
            "branches-covered": "0",
            "branches-valid": "0",
            "complexity": "0",
            "line-rate": "0.723",
            "lines-covered": "368",
            "lines-valid": "509",
            "timestamp": "1603825482736",
            "version": "5.0.4",
        }
        children = list(coverage_xml)
        assert len(children) == 2
        assert children[0].tag == "sources"

    def test_ignore_binary_coverage_data(self, tmp_path: Path, converter: WorkUnitConverter) -> None:
        context = FakePantsContext()
        converter.set_context(context)
        fixture_data = context.load_work_unit_fixture("pytest_with_coverage_binary")
        assert len(fixture_data) == 9  # sanity check
        transformed = converter.transform(fixture_data, 3, 44000)
        assert len(transformed) == 4
        all_work_units = converter.get_all_work_units(88, 111111)
        assert len(all_work_units) == 9
        wu_with_artifacts = [wu for wu in all_work_units if wu.get("artifacts")]
        assert len(wu_with_artifacts) == 0
        assert converter.get_standalone_artifacts() is None

    def test_work_units_with_counters_and_metadata(self, tmp_path: Path, converter: WorkUnitConverter) -> None:
        context = FakePantsContext()
        converter.set_context(context)
        fixture_data = context.load_work_unit_fixture("typecheck_with_counters")
        assert len(fixture_data) == 13  # sanity check
        transformed_map = {wu["workunit_id"]: wu for wu in converter.transform(fixture_data, 3, 44000)}
        assert len(transformed_map) == 13
        assert transformed_map["cae4a85f92c7050c"] == {
            "workunit_id": "cae4a85f92c7050c",
            "name": "multi_platform_process-running",
            "state": "finished",
            "version": 3,
            "parent_ids": ["ca26d462bc968fcd"],
            "last_update": 44000,
            "start_usecs": 1604376201340028,
            "description": "Run MyPy on 6 files.",
            "end_usecs": 1604376210560781,
        }
        assert transformed_map["cc2408c9f8c990c8"] == {
            "workunit_id": "cc2408c9f8c990c8",
            "name": "multi_platform_process-running",
            "state": "finished",
            "version": 3,
            "parent_ids": ["9ccd28609a415393"],
            "last_update": 44000,
            "start_usecs": 1604376201339386,
            "description": "Run MyPy on 38 files.",
            "end_usecs": 1604376219939610,
        }
        wu_map = {wu["workunit_id"]: wu for wu in converter.get_all_work_units(11, 22)}
        assert len(wu_map) == 13
        wu_with_artifacts = [wu for wu in wu_map.values() if wu.get("artifacts")]
        assert len(wu_with_artifacts) == 2
        assert converter.get_standalone_artifacts() is None
        assert wu_map["cae4a85f92c7050c"] == {
            "workunit_id": "cae4a85f92c7050c",
            "name": "multi_platform_process-running",
            "state": "finished",
            "version": 11,
            "parent_ids": ["ca26d462bc968fcd"],
            "last_update": 22,
            "start_usecs": 1604376201340028,
            "description": "Run MyPy on 6 files.",
            "end_usecs": 1604376210560781,
            "metadata": {"exit_code": 0, "definition": '{"argv":["./example"]}', "source": "HitLocally"},
            "counters": {"local_execution_requests": 1},
            "artifacts": {"stdout": "Success: no issues found in 6 source files\n"},
        }
        assert wu_map["cc2408c9f8c990c8"] == {
            "workunit_id": "cc2408c9f8c990c8",
            "name": "multi_platform_process-running",
            "state": "finished",
            "version": 11,
            "parent_ids": ["9ccd28609a415393"],
            "last_update": 22,
            "start_usecs": 1604376201339386,
            "description": "Run MyPy on 38 files.",
            "end_usecs": 1604376219939610,
            "metadata": {"exit_code": 0},
            "counters": {"local_execution_requests": 1},
            "artifacts": {"stdout": "Success: no issues found in 38 source files\n"},
        }
