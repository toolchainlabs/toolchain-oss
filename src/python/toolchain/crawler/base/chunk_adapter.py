# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import contextlib
from collections.abc import Iterator


class ChunkAdapter:
    """Endows an iterator over byte chunks with a read(n) method.

    Useful for wrapping the iter_content() generator of a requests Response object.
    """

    def __init__(self, chunk_iterator: Iterator[bytes]) -> None:
        self._chunk_iterator = chunk_iterator
        self._current_chunk: bytes = b""

    def read(self, size: int = -1) -> bytes:
        ret = b""
        if size <= 0:
            size = 1024**5  # 1T, so more than large enough to cover any size we actually care about.
        with contextlib.suppress(StopIteration):
            while size:  # The user asked for more than ret contains.
                if not self._current_chunk:
                    # The current chunk has been exhausted.
                    self._current_chunk = next(self._chunk_iterator)
                delta = self._current_chunk[0:size]
                self._current_chunk = self._current_chunk[len(delta) :]
                size -= len(delta)
                ret += delta
        return ret
