# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging

from toolchain.buildsense.ingestion.run_processors.common import FileInfo, RunArtifact

logger = logging.getLogger(__name__)

_CONTENT_TYPE = "targets_specs"


def get_targets(build_data: dict) -> RunArtifact:
    targets = build_data.get("targets")
    if not targets:
        return None
    artifact = [
        {
            "name": "Targets",
            "content_type": _CONTENT_TYPE,
            "content": targets,
        }
    ]
    targets_file = FileInfo.create_json_file("targets_specs", artifact)
    return targets_file, {
        "name": "targets_specs",
        "description": "Expanded targets specs",
        "artifacts": targets_file.name,
        "content_types": [_CONTENT_TYPE],
    }
