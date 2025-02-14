# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# This script is useful when we have issues with artifact extraction in production.
# The raw data file can be downloaded locally and we can run the artifact extraction logic and debug issues like:
# Extra artifacts -  artifacts that are not properly filtered out
# Goal identification issue
# To many artifact being extracted from a a single run.

import json
import sys
from pathlib import Path

from rich import print

from toolchain.buildsense.ingestion.run_processors.artifacts import GoalArtifactsExtractor
from toolchain.buildsense.ingestion.run_processors.artifacts_test import create_run_info


def parse_build(filename: str):
    build_stats = json.loads(Path(filename).read_bytes())
    run_info = create_run_info(build_stats, "3")
    extractor = GoalArtifactsExtractor.create()
    result = extractor.get_artifacts(run_info, build_stats, None)
    print(f"files: {[fn.name for fn in result.files]}")
    for fl in result.files:
        if "_artifacts" not in fl.name:
            continue
        print(fl.name)
        print(json.loads(fl.content))
        print("*" * 40)


if __name__ == "__main__":
    parse_build(sys.argv[0])
