# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import base64
import errno
import fileinput
import os
import shutil
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from tempfile import mkdtemp
from typing import Callable, Union

PathOrStr = Union[str, Path]


def _to_str(path: PathOrStr) -> str:
    return path if isinstance(path, str) else path.as_posix()


def walk_local_directory(local_dir: PathOrStr) -> Iterator[tuple[Path, Path]]:
    for dirpath, _, filenames in safe_os_walk(_to_str(local_dir)):
        for filename in sorted(filenames):
            path = Path(dirpath) / filename
            relpath = path.relative_to(local_dir)
            yield relpath, path


def safe_os_walk(path: PathOrStr) -> Iterator[tuple[str, list[str], list[str]]]:
    def error_handler(exception_instance):
        raise exception_instance

    return os.walk(_to_str(path), onerror=error_handler)


def safe_delete_dir(path: Path) -> None:
    with suppress(FileNotFoundError):
        shutil.rmtree(path.as_posix())
    if not path.exists():
        return
    for item in path.iterdir():
        if item.is_file():
            item.unlink()
        else:
            safe_delete_dir(item)


def safe_delete_file(path: Path) -> None:
    if path.exists():
        path.unlink()


def safe_copy_file(source: PathOrStr, target: PathOrStr) -> None:
    if os.path.exists(_to_str(target)):
        os.remove(_to_str(target))
    shutil.copy2(_to_str(source), _to_str(target))


def safe_mkdir(path: PathOrStr) -> None:
    """Create a directory (and all intermediate directories) without erroring if it already exists."""
    try:
        os.makedirs(_to_str(path))
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


@contextmanager
def temporary_dir(suffix="", prefix="tmp", directory=None, cleanup=True):
    """Yield a temporary directory in a context and clean it up when the context exits."""
    d = None
    try:
        d = mkdtemp(suffix, prefix, directory)
        yield d
    finally:
        if d and cleanup:
            shutil.rmtree(d)


@contextmanager
def read_from_files(paths):
    """Yield a file-like object that reads from each file, in order.

    Note: cannot passed as stdin when executing a subprocess.
    """
    fi = fileinput.FileInput(paths)
    try:
        yield fi
    finally:
        fi.close()


@contextmanager
def read_from_concatenated_files(paths):
    """Concatenate files into a temporary file, and yield its descriptor.

    Note: Can be passed as stdin when executing a subprocess.
    """
    with tempfile.NamedTemporaryFile(delete=True) as fp:
        for path in paths:
            with open(path) as inp:
                for line in inp:
                    fp.write(line)
        fp.seek(0)
        yield fp


def write_file(filename: PathOrStr, content: list | tuple | str) -> None:
    if isinstance(content, (list, tuple)):
        content = "\n".join(content)
    with open(_to_str(filename), "wb") as fp:
        fp.write(content.encode())


def read_file(filename: PathOrStr) -> str | None:
    try:
        with open(_to_str(filename), "rb") as fp:
            return fp.read().decode()
    except FileNotFoundError:
        return None


def short_random_filesafe_string() -> str:
    """Returns a 20 character random string that can be used in file paths."""
    # A full uuid can push the file name length beyond the max allowed (255).
    # We generate a shorter random suffix, to make this less likely.
    # We take the time in ms modulo 10000 seconds, plus a random string.
    return base64.urlsafe_b64encode(
        int(time.time() * 1000).to_bytes(length=6, byteorder="big") + os.urandom(9)
    ).decode()


@contextmanager
def safe_file_create(filename_or_path: str | Path, suffix: str | Callable = short_random_filesafe_string):
    """Yields a tmpfile that the caller can write to, which will be atomically copied to filename on success.

    If the context throws an exception, the tmpfile will be cleaned up and no file will be created at filename.
    """
    path = Path(filename_or_path) if isinstance(filename_or_path, str) else filename_or_path
    if path.exists():
        raise FileExistsError(path.as_posix())

    safe_mkdir(path.parent)
    if callable(suffix):
        suffix = suffix()
    filename_tmp = Path(f"{path.as_posix()}.{suffix}")
    try:
        yield filename_tmp
        filename_tmp.rename(path)
    finally:
        if filename_tmp.exists():
            filename_tmp.unlink()


@contextmanager
def pushd(directory):
    """Changes the cwd to the specified directory in the context."""
    old_cwd = os.getcwd()
    os.chdir(directory)
    try:
        yield
    finally:
        os.chdir(old_cwd)
