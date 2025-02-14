# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.util.leveldb import urls

base_dir_url = "s3://foo/bar/baz/"
leveldb = f"{base_dir_url}leveldbs/00456/"
input_list = f"{base_dir_url}input_lists/00456"
ordinal = 456


def test_ordinal_from_leveldb() -> None:
    assert ordinal == urls.ordinal_from_leveldb(leveldb)


def test_ordinal_from_input_list() -> None:
    assert ordinal == urls.ordinal_from_input_list(input_list)


def test_ordinal_from_input_list_invalid() -> None:
    with pytest.raises(urls.InvalidOrdinalError, match="Not a valid input list URL"):
        urls.ordinal_from_input_list("file:///data/leveldb/modules/input_lists/05701.7dABF3B7")


def test_leveldb_for_ordinal() -> None:
    assert leveldb == urls.leveldb_for_ordinal(base_dir_url, ordinal)


def test_input_list_for_ordinal() -> None:
    assert input_list == urls.input_list_for_ordinal(base_dir_url, ordinal)


def test_base_dir_url_from_leveldb() -> None:
    assert base_dir_url == urls.base_dir_url_from_leveldb(leveldb)


def test_base_dir_url_from_input_list() -> None:
    assert base_dir_url == urls.base_dir_url_from_input_list(input_list)


def test_input_list_for_leveldb() -> None:
    assert input_list == urls.input_list_for_leveldb(leveldb)


def test_leveldb_for_input_list() -> None:
    assert leveldb == urls.leveldb_for_input_list(input_list)
