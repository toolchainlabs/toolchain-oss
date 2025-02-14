# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from pants.version import VERSION as PANTS_VERSION

from toolchain.pants.version import VERSION as TOOLCHAIN_VERSION


def get_common_request_headers() -> dict[str, str]:
    return {"User-Agent": f"pants/v{PANTS_VERSION} toolchain/v{TOOLCHAIN_VERSION}"}
