# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from toolchain.util.file.create import create_directory, create_file
from toolchain.util.leveldb.urls import (
    input_list_base,
    input_list_for_ordinal,
    leveldb_for_ordinal,
    ordinal_from_input_list,
)


def find_ordinals(base_dir_url: str) -> list[int]:
    # The existence of an input list file signifies by convention that the corresponding leveldb is valid.
    return [ordinal_from_input_list(entry.url()) for entry in create_directory(input_list_base(base_dir_url)).list()]


def latest_ordinal(base_dir_url: str) -> int | None:
    """Return the ordinal of the latest valid leveldb found under the given dir."""
    try:
        return max(find_ordinals(base_dir_url))
    except ValueError:  # The arg to max() was an empty sequence.
        return None


def ordinal_exists(base_dir_url: str, ordinal: int) -> bool:
    """Returns whether a given ordinal exists under the given dir."""
    input_file_url = input_list_for_ordinal(base_dir_url, ordinal)
    return create_file(input_file_url).exists()


def latest(base_dir_url: str) -> str | None:
    """Return the latest valid leveldb found under the given dir."""
    try:
        latest_ordinal = max(find_ordinals(base_dir_url))
    except ValueError:  # The arg to max() was an empty sequence.
        return None
    return leveldb_for_ordinal(base_dir_url, latest_ordinal)
