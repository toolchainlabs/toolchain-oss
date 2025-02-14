# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import contextlib
import os
from pathlib import Path

import pytest

from toolchain.base.fileutil import safe_file_create, short_random_filesafe_string

_dummy_tmp_suffix = "for_test"


def test_safe_file_create(tmp_path: Path) -> None:
    """Test that the success path works as expected."""
    hello_world = b"Hello, World!"
    filename = tmp_path / "foo" / "helloworld.txt"
    filename_tmp = f"{filename.as_posix()}.{_dummy_tmp_suffix}"
    assert not os.path.exists(filename_tmp)

    with safe_file_create(filename, suffix=_dummy_tmp_suffix) as tmpfile:
        with open(tmpfile, "wb") as fp:
            fp.write(hello_world)
        assert os.path.exists(filename_tmp)
        assert not os.path.exists(filename)
    assert not os.path.exists(filename_tmp)
    assert os.path.exists(filename)

    with open(filename, "rb") as fp:
        content = fp.read()
    assert hello_world == content


def test_safe_file_create_with_generator(tmp_path: Path) -> None:
    """Test that the success path works as expected."""
    generator_calls = []

    def suffix_generator():
        generator_calls.append("dummy")
        return _dummy_tmp_suffix

    hello_world = b"Hello, World!"
    filename = tmp_path / "foo" / "helloworld.txt"
    filename_tmp = f"{filename.as_posix()}.{_dummy_tmp_suffix}"
    assert not os.path.exists(filename_tmp)

    with safe_file_create(filename, suffix=suffix_generator) as tmpfile:
        with open(tmpfile, "wb") as fp:
            fp.write(hello_world)
        assert os.path.exists(filename_tmp)
        assert not os.path.exists(filename)
    assert not os.path.exists(filename_tmp)
    assert os.path.exists(filename)
    assert len(generator_calls) == 1
    content = filename.read_bytes()
    assert hello_world == content


def test_safe_file_create_cleanup(tmp_path: Path) -> None:
    """Test that the failure path cleans up the tmpfile (and doesn't create the final file)."""

    class DummyException(Exception):
        pass

    filename = tmp_path / "foo" / "bar"
    filename_tmp = f"{filename.as_posix()}.{_dummy_tmp_suffix}"
    assert not os.path.exists(filename_tmp)

    with contextlib.suppress(DummyException), safe_file_create(filename, suffix=_dummy_tmp_suffix) as tmpfile:
        with tmpfile.open(mode="wb"):
            pass
        assert os.path.exists(filename_tmp)
        assert not os.path.exists(filename)
        raise DummyException("ooops, something happened")

    assert not os.path.exists(filename_tmp)
    assert not os.path.exists(filename)


def test_safe_file_create_exists(tmp_path: Path) -> None:
    """Test that we cannot safe-create over an existing file."""
    filename = tmp_path / "foo"
    with filename.open(mode="wb"):
        pass
    with pytest.raises(FileExistsError, match=filename.as_posix()), safe_file_create(
        filename, suffix=_dummy_tmp_suffix
    ):
        pass


def test_short_random_filesafe_string() -> None:
    assert len(short_random_filesafe_string()) == 20
