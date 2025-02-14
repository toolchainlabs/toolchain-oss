# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from pathlib import Path

import plyvel

from toolchain.util.leveldb.merge import merge_tables


def _bytes(s):
    return s.encode("ascii")


def test_merge_tables(tmp_path: Path) -> None:
    input_tables = []
    for i in range(0, 10):
        input_table = plyvel.DB((tmp_path / f"input_table_{i}").as_posix(), create_if_missing=True)
        input_tables.append(input_table)
        for j in range(i, 200, 10):
            input_table.put(_bytes(f"K{j:03d}"), _bytes(f"V{j:03d}"))

    output_table = plyvel.DB((tmp_path / "output_table").as_posix(), create_if_missing=True)
    merge_tables(input_tables, output_table)

    merged_items = []
    for k, v in output_table.iterator():
        merged_items.append((k, v))

    expected_items = [(_bytes(f"K{i:03d}"), _bytes(f"V{i:03d}")) for i in range(0, 200)]
    assert expected_items == merged_items
