# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import plyvel

from toolchain.util.leveldb.dataset import Dataset


class FakeReloadableDataset:
    def __init__(self, fake_dataset: Dataset) -> None:
        self._dataset = fake_dataset

    @contextmanager
    def get(self) -> Iterator[Dataset]:
        yield self._dataset


def write_level_db(tmp_path: Path, items: Iterator[tuple[bytes, bytes]]) -> None:
    db = plyvel.DB(tmp_path.as_posix(), create_if_missing=True)
    with db.write_batch() as batch:
        for key, value in items:
            batch.put(key, value)
    db.compact_range()
    db.close()
