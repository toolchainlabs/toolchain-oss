# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from collections.abc import Iterator

import pytest

from toolchain.crawler.base.chunk_adapter import ChunkAdapter


# Mocks the generator returned by Response.iter_content().
def iter_content(content: bytes, chunk_size: int) -> Iterator[bytes]:
    yield from [content[i : i + chunk_size] for i in range(0, len(content), chunk_size)]


@pytest.mark.parametrize("content", [b"", b"X", b"XX", b"Bizarro Jerry" * 777, b"\x7fELF\x01\x01\x01\0" * 32])
@pytest.mark.parametrize("orig_chunk_size", [1, 2, 3, 7, 23, 100, 1000, 10000, 100000])
@pytest.mark.parametrize("read_block_size", [-1, 1, 2, 3, 7, 23, 100, 1000, 10000, 100000])
def test_response_adapter(content: bytes, orig_chunk_size: int, read_block_size: int) -> None:
    ca = ChunkAdapter(iter_content(content, orig_chunk_size))
    reassembled_bytes = b""
    read_block = ca.read(read_block_size)
    while read_block:
        reassembled_bytes += read_block
        read_block = ca.read(read_block_size)

    assert content == reassembled_bytes
