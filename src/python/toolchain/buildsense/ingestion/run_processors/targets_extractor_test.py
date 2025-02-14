# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json

from toolchain.buildsense.ingestion.run_processors.targets_extractor import get_targets
from toolchain.buildsense.test_utils.fixtures_loader import load_fixture


def test_get_targets() -> None:
    build_data = load_fixture("run_test_with_targets_data")
    target_data = get_targets(build_data)
    assert target_data is not None
    targets_file, artifact_dict = target_data
    assert artifact_dict == {
        "name": "targets_specs",
        "description": "Expanded targets specs",
        "artifacts": "targets_specs.json",
        "content_types": ["targets_specs"],
    }
    assert targets_file.name == "targets_specs.json"
    assert targets_file.content_type == "application/json"
    targets_artifacts = json.loads(targets_file.content)

    targets = targets_artifacts[0].pop("content")
    assert targets_artifacts == [{"name": "Targets", "content_type": "targets_specs"}]
    assert isinstance(targets, dict)
    assert len(targets) == 11
    assert "src/python/toolchain/users/jwt" in targets
    assert targets["src/python/toolchain/users/management/commands"] == [
        {"filename": "src/python/toolchain/users/management/commands/bootstrap.py"},
        {"filename": "src/python/toolchain/users/management/commands/configure_checkers.py"},
    ]


def test_get_targets_no_targets() -> None:
    build_data = load_fixture("run_typecheck_with_metrics.legacy_counters")
    assert get_targets(build_data) is None
