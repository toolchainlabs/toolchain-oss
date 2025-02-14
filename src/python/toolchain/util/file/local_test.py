# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from toolchain.util.file.local import LocalDirectory, LocalFile


def test_url_and_path():
    file = LocalFile("/foo/bar/baz")
    assert file.url() == "file:///foo/bar/baz"
    assert file.path() == "/foo/bar/baz"


def test_file_exists_and_delete(tmp_path: Path) -> None:
    path = tmp_path / "foo.txt"
    with open(path, "wb") as fp:
        fp.write(b"")
    lf = LocalFile(path.as_posix())
    assert lf.exists()
    lf.delete()
    assert not lf.exists()


def test_file_set_and_get_content() -> None:
    with NamedTemporaryFile() as tmpfile:
        content = b"Hello, World!"
        file = LocalFile(tmpfile.name)
        file.set_content(content)
        assert content == file.get_content()


def test_file_copy_local_to_local(tmp_path: Path) -> None:
    content = b"Hello, World!"
    src_path = tmp_path / "foo.txt"
    dst_path = tmp_path / "bar.txt"
    src = LocalFile(src_path.as_posix())
    dst = LocalFile(dst_path.as_posix())

    assert not src.exists()
    assert not dst.exists()

    with open(src_path, "wb") as fp:
        fp.write(content)
    assert src.exists()
    assert not dst.exists()

    src.copy_to(dst)
    assert src.exists()
    assert dst.exists()
    assert content == dst.get_content()

    dst.delete()
    assert src.exists()
    assert not dst.exists()

    dst.copy_from(src)
    assert src.exists()
    assert dst.exists()
    assert content == dst.get_content()


def test_directory_get_file() -> None:
    assert LocalFile(os.path.join(os.path.sep, "foo", "bar", "baz", "qux.txt")) == LocalDirectory(
        os.path.join(os.path.sep, "foo", "bar")
    ).get_file("baz/qux.txt")


def test_directory_traverse(tmp_path: Path) -> None:
    relpaths = (
        Path("foo.txt"),
        Path("bar") / "baz.txt",
        Path("bar") / "qux" / "quux.txt",
        Path("a") / "b" / "c" / "d",
    )

    for relpath in relpaths:
        path = tmp_path / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as fp:
            fp.write(b"")

    expected_files = {LocalFile((tmp_path / relpath).as_posix()) for relpath in relpaths}
    assert expected_files == set(LocalDirectory(tmp_path.as_posix()).traverse())


def test_directory_delete(tmp_path: Path) -> None:
    path = tmp_path / "foo"
    path.mkdir()
    with open(os.path.join(path, "bar.txt"), "wb") as fp:
        fp.write(b"")
    baz = path / "baz"
    baz.mkdir()

    LocalDirectory(path.as_posix()).delete()
    assert path.is_dir() is False


def test_directory_copy_local_to_local(tmp_path: Path) -> None:
    src_path = tmp_path / "src"
    dst_path = tmp_path / "dst"

    (src_path / "foo").mkdir(parents=True)
    with open(os.path.join(src_path, "foo", "bar.txt"), "wb") as fp:
        fp.write(b"bar")
    baz = src_path / "baz"
    baz.mkdir()
    with open(baz / "qux.txt", "wb") as fp:
        fp.write(b"qux")
    with open(os.path.join(src_path, "baz", "quux.txt"), "wb") as fp:
        fp.write(b"quux")

    src = LocalDirectory(src_path.as_posix())
    dst = LocalDirectory(dst_path.as_posix())

    src.copy_to(dst)
    assert LocalFile((Path(dst_path) / "foo" / "bar.txt").as_posix()).get_content() == b"bar"
    assert LocalFile((Path(dst_path) / "baz" / "qux.txt").as_posix()).get_content() == b"qux"
    assert LocalFile((Path(dst_path) / "baz" / "quux.txt").as_posix()).get_content() == b"quux"

    src.delete()
    src.copy_from(dst)
    assert LocalFile((Path(src_path) / "foo" / "bar.txt").as_posix()).get_content() == b"bar"
    assert LocalFile((Path(src_path) / "baz" / "qux.txt").as_posix()).get_content() == b"qux"
    assert LocalFile((Path(src_path) / "baz" / "quux.txt").as_posix()).get_content() == b"quux"
