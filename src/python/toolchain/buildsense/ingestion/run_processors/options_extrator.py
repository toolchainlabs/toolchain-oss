# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging

from toolchain.buildsense.ingestion.run_processors.common import FileInfo, RunArtifact

logger = logging.getLogger(__name__)

_CONTENT_TYPE = "pants_options"


def get_pants_options(build_data: dict) -> RunArtifact:
    options = build_data.get("recorded_options")
    if not options:
        return None
    artifact = [
        {
            "name": "Options",
            "content_type": _CONTENT_TYPE,
            "content": options,
        }
    ]
    options_file = FileInfo.create_json_file("pants_options", artifact)
    return options_file, {
        "name": "pants_options",
        "description": "Pants Options",
        "artifacts": options_file.name,
        "content_types": [_CONTENT_TYPE],
    }
