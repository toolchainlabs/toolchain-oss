# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.util.leveldb.syncer import Syncer


def test_syncer(tmp_path) -> None:
    remote_dir = tmp_path / "remote"
    local_dir = tmp_path / "local"
    remote_dir.mkdir()
    local_dir.mkdir()

    syncer = Syncer(f"file://{remote_dir}/", f"file://{local_dir}/")

    leveldbs = remote_dir / "leveldbs"
    input_lists = remote_dir / "input_lists"
    leveldbs.mkdir()
    input_lists.mkdir()

    (leveldbs / "00023").mkdir()
    (leveldbs / "00023" / "dummy").write_text("")
    (input_lists / "00023").write_text("")

    syncer.check_latest()
    assert syncer.get_latest_local_ordinal() == 23
    assert syncer.get_stale_ordinals() == []

    (leveldbs / "00024").mkdir()
    (leveldbs / "00024" / "dummy").write_text("")
    (input_lists / "00024").write_text("")

    syncer.check_latest()
    assert syncer.get_latest_local_ordinal() == 24
    assert syncer.get_stale_ordinals() == [23]

    syncer.cleanup()
    assert syncer.get_latest_local_ordinal() == 24
    assert syncer.get_stale_ordinals() == []
