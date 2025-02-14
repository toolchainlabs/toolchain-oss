# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import pytest

from toolchain.crawler.pypi.data_dump_sharding import BadSharding, compute_seed_shards


@pytest.mark.parametrize(
    ("num_shards", "concurrency", "expected_seed_shards"),
    [
        (1, 1, (0,)),
        (16, 1, (0,)),
        (16, 2, (0, 8)),
        (16, 4, (0, 4, 8, 12)),
        (16, 8, (0, 2, 4, 6, 8, 10, 12, 14)),
        (256, 1, (0,)),
        (256, 2, (0, 128)),
        (256, 4, (0, 64, 128, 192)),
        (256, 8, (0, 32, 64, 96, 128, 160, 192, 224)),
    ],
)
def test_compute_seed_shards(num_shards: int, concurrency: int, expected_seed_shards: tuple[int, ...]) -> None:
    assert expected_seed_shards == compute_seed_shards(num_shards, concurrency)


@pytest.mark.parametrize("num_shards", [15, 17, 32, 64, 255, 0, -1])
def test_compute_seed_shards_invalid_num_shards(num_shards):
    with pytest.raises(BadSharding, match=r"Number of shards must be one of \(1, 16, 256\)"):
        compute_seed_shards(num_shards, 1)


@pytest.mark.parametrize(
    ("num_shards", "concurrency"),
    [
        (1, 0),
        (1, 2),
        (1, -1),
        (16, 0),
        (16, 3),
        (16, 7),
        (16, 10),
        (16, 17),
        (16, 32),
        (16, 64),
        (16, -1),
        (256, 0),
        (256, 3),
        (256, 10),
        (256, 65),
        (256, 255),
        (256, 257),
        (256, 512),
        (256, -1),
    ],
)
def test_compute_seed_shards_invalid_concurrency(num_shards: int, concurrency: int) -> None:
    with pytest.raises(BadSharding, match=f"Concurrency value was {concurrency} but must be one of .*"):
        compute_seed_shards(num_shards, concurrency)
