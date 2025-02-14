# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from collections.abc import Sequence

import plyvel

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.util.file.base import Directory, File
from toolchain.util.file.create import create, create_directory
from toolchain.util.file.local import LocalDirectory

logger = logging.getLogger(__name__)


class Builder:
    """Utility code to build a leveldb table from some input data."""

    def __init__(
        self,
        input_urls: Sequence[str],
        output_dir_url: str,
        existing_leveldb_dir_url: str,
        write_batch_size: int = 100000,
    ) -> None:
        self._inputs = [create(url) for url in input_urls]
        self._existing_leveldb_dir = create_directory(existing_leveldb_dir_url) if existing_leveldb_dir_url else None
        self._output_dir = create_directory(output_dir_url)
        self._write_batch_size = write_batch_size
        self._db: plyvel.DB | None = None
        self._write_batch: plyvel.WriteBatch | None = None
        self._num_items = 0

    def filter_input_file(self, input_file: File) -> bool:
        """Should we process this file?"""
        return True

    def process_input_file(self, input_file: File) -> None:
        """Process the input file."""
        raise NotImplementedError

    def item_handled(self) -> None:
        """Register that an item has been handled, whether or not it has been put() yet."""
        self._num_items += 1
        if self._num_items % self._write_batch_size == 0:
            self.flush()

    def put(self, key: bytes, value: bytes) -> None:
        if self._write_batch is None:
            raise ToolchainAssertion("No active write batch")
        self._write_batch.put(key, value)

    def flush(self) -> None:
        if self._db is None:
            raise ToolchainAssertion("No active levelDB")
        if self._write_batch is None:
            raise ToolchainAssertion("No active write batch")
        self._write_batch.write()
        self._write_batch = self._db.write_batch()
        logger.info(f"Flushed {self._num_items:,} items.")

    @property
    def db(self) -> plyvel.DB:
        """The db being built.

        Subclasses can query the data created so far (up to the last batch) in their process_input_file().
        """
        return self._db

    def run(self) -> None:
        input_files: list[File] = []
        for inp in self._inputs:
            if isinstance(inp, Directory):
                logger.info(f"Collecting files from {inp}")
                input_files.extend(input_file for input_file in inp.traverse() if self.filter_input_file(input_file))
            else:
                logger.info(f"Collecting file {inp}")
                input_files.append(inp)  # type: ignore
        with LocalDirectory.temp() as tmpdir:
            logger.info(f"Creating leveldb in {tmpdir}")
            if self._existing_leveldb_dir and self._existing_leveldb_dir.get_file("CURRENT").exists():
                logger.info(f"Copying existing data from {self._existing_leveldb_dir}")
                self._existing_leveldb_dir.copy_to(tmpdir)
            self._db = plyvel.DB(tmpdir.path(), create_if_missing=True)
            self._write_batch = self._db.write_batch()  # type: ignore

            for idx, input_file in enumerate(input_files):
                logger.info(f"Processing {idx:,}/{len(input_files):,} - {input_file}")
                self.process_input_file(input_file)
            self.flush()

            logger.info("Performing final leveldb compaction")
            self._db.compact_range()
            self._db.close()

            logger.info(f"leveldb created. Copying leveldb to {self._output_dir}.")
            self._output_dir.delete()
            tmpdir.copy_to(self._output_dir)
            logger.debug("Done!")
