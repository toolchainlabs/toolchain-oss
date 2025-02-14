# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from argparse import ArgumentParser

from prometheus_client import Histogram

from toolchain.base.contexttimer import Timer
from toolchain.base.env_args import StoreWithEnvDefault
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.util.file.argument_types import directory_url, local_directory_url
from toolchain.util.leveldb.latest import find_ordinals, latest
from toolchain.util.leveldb.urls import copy_leveldb_and_input_list, delete_leveldb_and_input_list, ordinal_from_leveldb

logger = logging.getLogger(__name__)

LEVEL_DB_FETCH_LATENCY = Histogram(
    name="toolchain_dependency_level_db_fetch_latency",
    documentation="Histogram of level db sync (fetch) time, by level_db name.",
    labelnames=["db_name", "db_ordinal"],
    buckets=(0.5, 3, 8, 10, 20, 30, 40, 50, 90, 180, 360, float("inf")),
)


class Syncer:
    """Syncs a remote dataset to a local directory."""

    def __init__(self, remote_basedir_url: str, local_basedir_url: str) -> None:
        self._remote_basedir_url = remote_basedir_url
        self._local_basedir_url = local_basedir_url
        parts = remote_basedir_url.split("/")
        # if remote_basedir_url ends with '/' then parts[-1] will be an empty string
        self._name = parts[-1] or parts[-2]

    def get_latest_local_ordinal(self) -> int:
        latest_local = latest(self._local_basedir_url)
        return -1 if latest_local is None else ordinal_from_leveldb(latest_local)

    def check_latest(self) -> None:
        latest_local_ordinal = self.get_latest_local_ordinal()
        logger.info(
            f"{self._name} Current local leveldb ordinal: {latest_local_ordinal} checking latest in {self._remote_basedir_url}"
        )
        latest_path = latest(self._remote_basedir_url)
        if not latest_path:
            logger.warning(f"{self._name} No leveldb found in {self._remote_basedir_url}")
            return
        latest_remote_ordinal = ordinal_from_leveldb(latest_path)
        if latest_remote_ordinal == latest_local_ordinal:
            logger.debug(f"{self._name} Already at latest leveldb: {latest_remote_ordinal:05}.")
        else:
            self.fetch(latest_remote_ordinal)

    def get_stale_ordinals(self) -> list[int]:
        ordinals = find_ordinals(self._local_basedir_url)
        return [ordinal for ordinal in ordinals if ordinal < self.get_latest_local_ordinal()]

    def fetch(self, ordinal: int) -> None:
        logger.info(f"{self._name} Fetching latest leveldb: {ordinal:05}.")
        with Timer() as timer:
            copy_leveldb_and_input_list(self._remote_basedir_url, self._local_basedir_url, ordinal)
        LEVEL_DB_FETCH_LATENCY.labels(db_name=self._name, db_ordinal=str(ordinal)).observe(timer.elapsed)
        logger.info(f"Fetched leveldb={self._name} ordinal={ordinal:05} latency={timer.elapsed:.3f}s")

    def cleanup(self) -> None:
        logger.debug(f"{self._name} Looking for cleanup work.")
        for ordinal in self.get_stale_ordinals():
            delete_leveldb_and_input_list(self._local_basedir_url, ordinal)


class SyncerTool(ToolchainBinary):
    """Syncs a remote dataset to a local directory."""

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--remote-basedir-url",
            type=directory_url,
            required=True,
            action=StoreWithEnvDefault,
            help="URL of remote base dir containing leveldbs.",
        )
        parser.add_argument(
            "--local-basedir-url",
            type=local_directory_url,
            required=True,
            action=StoreWithEnvDefault,
            help="URL of local base dir to fetch leveldbs to.",
        )

    def run(self) -> int:
        syncer = Syncer(self.cmdline_args.remote_basedir_url, self.cmdline_args.local_basedir_url)
        syncer.check_latest()
        return 0


if __name__ == "__main__":
    SyncerTool.start()
