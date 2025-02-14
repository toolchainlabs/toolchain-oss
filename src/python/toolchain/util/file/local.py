# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager

from toolchain.base.fileutil import safe_mkdir, safe_os_walk, temporary_dir
from toolchain.base.memo import memoized
from toolchain.util.file.base import Directory, File


class LocalMixin:
    """A mixin containing common implementation details for local files and directories."""

    def __init__(self, os_path: str):
        if not os_path.startswith(os.path.sep):
            raise AssertionError(f"Path must be absolute, but got {os_path}")
        self._os_path = os_path

    @property
    def os_path(self) -> str:
        return self._os_path

    @memoized
    def url(self) -> str:
        return f"file://{self.path()}"

    @memoized
    def path(self) -> str:
        # This method returns the path component of the URL, which always uses forward slashes.
        return self._os_path if os.path.sep == "/" else self._os_path.replace(os.path.sep, "/")

    def __eq__(self, other):
        return isinstance(other, type(self)) and self._os_path == other._os_path

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self._os_path)

    def __repr__(self):
        return f"{self.__class__.__name__}({self._os_path})"


class LocalFile(LocalMixin, File):
    def exists(self) -> bool:
        return os.path.exists(self._os_path)

    def get_content(self) -> bytes:
        with open(self._os_path, "rb") as fp:
            return fp.read()

    def set_content(self, buf: bytes):
        with open(self._os_path, "wb") as fp:
            fp.write(buf)

    def delete(self):
        os.unlink(self._os_path)

    # Note that LocalFile doesn't know about any other subclasses of File, and delegates copying to them.

    def copy_to(self, dst: File):
        if isinstance(dst, LocalFile):
            safe_mkdir(os.path.dirname(dst._os_path))
            shutil.copy(self._os_path, dst._os_path)
        else:
            dst.copy_from(self)

    def copy_from(self, src: File):
        if isinstance(src, LocalFile):
            safe_mkdir(os.path.dirname(self._os_path))
            shutil.copy(src._os_path, self._os_path)
        else:
            src.copy_to(self)


class LocalDirectory(LocalMixin, Directory):
    @classmethod
    @contextmanager
    def temp(cls):
        with temporary_dir() as tmpdir:
            yield cls(tmpdir)

    def __init__(self, os_path: str):
        # Ensure a slash suffix even if we create these directly in tests.
        if not os_path.endswith(os.path.sep):
            os_path = f"{os_path}{os.path.sep}"
        super().__init__(os_path)

    def get_file(self, suffix: str) -> File:
        relpath = suffix if os.path.sep == "/" else suffix.replace("/", os.path.sep)
        return LocalFile(os.path.join(self._os_path, relpath))

    def traverse(self) -> Iterator[File]:
        if not os.path.exists(self._os_path):
            return
        for dirpath, _, filenames in safe_os_walk(self._os_path):
            for filename in sorted(filenames):
                yield LocalFile(os.path.join(dirpath, filename))

    def delete(self):
        if os.path.exists(self._os_path):
            shutil.rmtree(self._os_path)
