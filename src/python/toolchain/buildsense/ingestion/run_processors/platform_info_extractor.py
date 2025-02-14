# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from toolchain.buildsense.ingestion.run_processors.common import PLATFORM_INFO_FILE_NAME, FileInfo


def get_platform_info(build_data: dict) -> FileInfo | None:
    platform_info = build_data.get("platform")
    return FileInfo.create_json_file(PLATFORM_INFO_FILE_NAME, platform_info) if platform_info else None
