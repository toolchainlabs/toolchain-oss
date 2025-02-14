# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import atexit
import logging
import shutil
from pathlib import Path
from tempfile import mkdtemp
from typing import TypeVar

import plyvel

from toolchain.base.toolchain_error import ToolchainError
from toolchain.util.file.create import create_directory, create_directory_from_path
from toolchain.util.file.local import LocalDirectory
from toolchain.util.leveldb.urls import ordinal_from_leveldb


class DatasetLoadError(ToolchainError):
    """Raised when we fail to open load a dataset."""


logger = logging.getLogger(__name__)


T = TypeVar("T", bound="Dataset")


class Dataset:
    """Base class for classes that query a leveldb."""

    lru_cache_size_mb = 100

    @classmethod
    def open_leveldb(cls, path: str) -> plyvel.DB:
        try:
            return plyvel.DB(name=path, create_if_missing=False, lru_cache_size=cls.lru_cache_size_mb * 1024 * 1024)
        except plyvel.CorruptionError as error:
            logger.warning(f"Failed to open level db at {path} - {error!r}", exc_info=True)
            raise DatasetLoadError(f"Failed to open level db at {path} - {error}")

    @classmethod
    def from_url(cls: type[T], leveldb_url: str, always_copy: bool = False, tmpdir: str | None = None) -> T:
        """Create a dataset from the data at the given URL.

        The data may be copied to a tmpdir, to work around leveldb's LOCK mechanism.
        TODO: Find an sstable-like read-only data structure as efficient as leveldb, but without the locking concerns.
        """
        source_dir = create_directory(leveldb_url)

        # See if we can use the source directly.
        if not always_copy and isinstance(source_dir, LocalDirectory):
            local_path = source_dir.os_path
            try:
                # Note that if we use the source directly, we don't clean it up.
                logger.info(f"Using leveldb at {leveldb_url} directly.")
                return cls(cls.open_leveldb(local_path), leveldb_url, cleanup=False)
            except plyvel.IOError as error:  # Lock is already held by some process (possibly even this one).
                logger.warning(f"Failed to load leveldb at url={leveldb_url} path={local_path} {error}")

        tmpdir = tmpdir or mkdtemp()
        try:
            source_dir.copy_to(create_directory_from_path(Path(tmpdir)))
        except FileNotFoundError as error:
            raise DatasetLoadError(f"Couldn't copy to tmpdir={tmpdir} - {error}")
        logger.info(f"Using copy of leveldb at {leveldb_url} in {tmpdir}")
        return cls(cls.open_leveldb(tmpdir), leveldb_url, cleanup=True)

    @classmethod
    def from_path(cls: type[T], path: str, always_copy: bool = False, tmpdir: str | None = None) -> T:
        return cls.from_url(f"file://{path}/", always_copy=always_copy, tmpdir=tmpdir)

    def __init__(self, db: plyvel.DB, source_url: str, cleanup: bool):
        """Callers should generally use from_url() or from_path() instead of calling this directly."""
        self._db = db
        self._source_url = source_url
        self._cleanup = cleanup

    @property
    def db(self) -> plyvel.DB:
        return self._db

    @property
    def source_url(self) -> str:
        return self._source_url

    @property
    def db_version(self) -> int:
        return ordinal_from_leveldb(self.source_url)

    def close(self) -> None:
        logger.info(f"Close {self} cleanup={self._cleanup}")
        self._db.close()
        if self._cleanup:
            shutil.rmtree(self._db.name)

    def autoclose(self) -> None:
        atexit.register(self.close)

    def __str__(self) -> str:
        return f"{type(self).__name__} - source={self.source_url}"
