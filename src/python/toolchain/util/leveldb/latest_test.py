# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.util.leveldb.latest import latest, ordinal_exists


def test_latest(tmp_path) -> None:
    def get_latest():
        return latest(f"{tmp_path.as_uri()}/")

    leveldbs = tmp_path / "leveldbs"
    input_lists = tmp_path / "input_lists"

    leveldbs.mkdir()
    input_lists.mkdir()

    assert get_latest() is None

    (leveldbs / "00023").mkdir()
    (input_lists / "00023").write_text("")
    assert get_latest() == f'{(leveldbs / "00023").as_uri()}/'

    (leveldbs / "00024").mkdir()
    (input_lists / "00024").write_text("")
    assert get_latest() == f'{(leveldbs / "00024").as_uri()}/'

    (leveldbs / "00022").mkdir()
    (input_lists / "00022").write_text("")
    assert get_latest() == f'{(leveldbs / "00024").as_uri()}/'


def test_ordinal_exists(tmp_path) -> None:
    leveldbs = tmp_path / "leveldbs"
    input_lists = tmp_path / "input_lists"
    dir_base = f"{tmp_path.as_uri()}/"
    leveldbs.mkdir()
    input_lists.mkdir()

    assert ordinal_exists(dir_base, 3001) is False
    (leveldbs / "03001").write_text("gold jerry gold!")
    (leveldbs / "3001").write_text("gold jerry gold!")
    (input_lists / "3001").write_text("gold jerry gold!")
    assert ordinal_exists(dir_base, 3001) is False
    (input_lists / "03001").write_text("gold jerry gold!")
    assert ordinal_exists(dir_base, 3001) is True
    assert ordinal_exists(dir_base, 1) is False
    (input_lists / "00001").write_text("gold jerry gold!")
    assert ordinal_exists(dir_base, 1) is True
