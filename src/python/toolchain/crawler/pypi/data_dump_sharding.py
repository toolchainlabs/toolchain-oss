# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import math

from toolchain.base.toolchain_error import ToolchainAssertion

# Utilities for sharding data dumps to control database load.

NUM_SHARDS_CHOICES = (1, 16, 256)


class BadSharding(ToolchainAssertion):
    pass


def compute_seed_shards(num_shards: int, concurrency: int) -> tuple[int, ...]:
    if num_shards not in NUM_SHARDS_CHOICES:
        raise BadSharding(f"Number of shards must be one of {NUM_SHARDS_CHOICES}")
    if num_shards == 1:
        valid_concurrency_values = (1,)
    else:
        valid_concurrency_values = tuple((2**exp) for exp in range(0, int(math.log2(num_shards))))  # type: ignore

    if concurrency not in valid_concurrency_values:
        raise BadSharding(f"Concurrency value was {concurrency} but must be one of {valid_concurrency_values}")

    step = int(num_shards / concurrency)
    return tuple(range(0, num_shards, step))
