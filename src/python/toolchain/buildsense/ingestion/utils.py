# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
import zlib

from toolchain.base.contexttimer import Timer
from toolchain.base.toolchain_error import ToolchainError

_logger = logging.getLogger(__name__)


class DecompressFailed(ToolchainError):
    pass


def decompress(context: str, data: bytes) -> bytes:
    with Timer(factor=1000) as timer:
        try:
            uncompressed = zlib.decompress(data)
        except zlib.error as error:
            _logger.warning(f"Failed to decompress {context} data: {error!r}")
            raise DecompressFailed(f"Failed to decompress data: {error!r}")
    ratio = len(data) / len(uncompressed)
    _logger.info(
        f"buildsense_decompress {context} compressed={len(data):,} uncompressed={len(uncompressed):,} {ratio=:.2%} latency_msec={timer.elapsed:.3f}"
    )
    return uncompressed
