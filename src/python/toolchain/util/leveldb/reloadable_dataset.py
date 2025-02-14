# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from threading import Thread
from time import sleep

from prometheus_client import Counter, Gauge

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.util.leveldb.dataset import Dataset, DatasetLoadError
from toolchain.util.leveldb.latest import latest
from toolchain.util.leveldb.urls import InvalidOrdinalError, ordinal_from_leveldb

LATEST_LEVEL_DB_ORDINAL = Gauge(
    name="toolchain_dependency_latest_level_db",
    documentation="Latest LevelDB ordinal by level DB name",
    labelnames=["db_name"],
    multiprocess_mode="liveall",
)

LEVEL_DB_UPDATE_CHECK = Counter(
    name="toolchain_dependency_latest_level_db_update_check",
    documentation="Counter of update checks for level db",
    labelnames=["db_name", "context"],
)


_logger = logging.getLogger(__name__)


class ReloadableDataset:
    """Polls for new leveldbs under a (typically local) dir and loads the latest one as a Dataset.

    Typically used in concert with Watcher. A Watcher polls a remote dir and downloads new leveldbs to a local dir. A
    ReloadableDataset polls that local dir and reloads the latest data.  This prevents multiple processes from directly
    polling and downloading the remote dir.
    """

    def __init__(self, dataset_cls: type[Dataset], basedir_url: str, period_secs: float, start: bool = False) -> None:
        # Note that we are relying on the fact that reading and setting these variables is atomic in CPython.
        self._period_secs = period_secs
        self._basedir_url = basedir_url
        self._reloader_thread: Thread | None = None
        _logger.info(
            f"Init ReloadableDataset for {dataset_cls.__name__} basedir_url={basedir_url} period_secs={period_secs}"
        )

        self._current_dataset: Dataset | None = None  # Initialized lazily, see get().
        self._lock = threading.Lock()  # Protects the self._current_dataset reference.
        self._stop: bool = False
        self._dataset_cls = dataset_cls
        self._db_name = dataset_cls.__name__.lower()
        if start:
            self.start()

    def _check_for_update(self, ctx, current=None) -> Dataset:
        latest_leveldb = latest(self._basedir_url)
        LEVEL_DB_UPDATE_CHECK.labels(db_name=self._db_name, context=ctx).inc()
        _logger.debug(f"Check for update. ctx={ctx} latest={latest_leveldb} current={current}")
        if latest_leveldb is None:
            raise ToolchainAssertion(f"No leveldbs found under {self._basedir_url}")
        if current is None or current.source_url != latest_leveldb:
            return self._dataset_cls.from_url(latest_leveldb)
        return current

    def _update_loop(self) -> None:
        sleep_period = self._period_secs
        while not self._stop:
            sleep(sleep_period)
            try:
                new_dataset = self._check_for_update("loop", self._current_dataset)
            except DatasetLoadError as error:
                sleep_period = 20
                _logger.warning(f"Loading dataset failed {error}")
                continue
            except InvalidOrdinalError as error:
                sleep_period = 20
                _logger.warning(f"Failed to find ordinal. {error!r}")
                continue
            sleep_period = self._period_secs
            latest_ordinal = ordinal_from_leveldb(new_dataset.source_url)
            LATEST_LEVEL_DB_ORDINAL.labels(db_name=self._db_name).set(latest_ordinal)
            if new_dataset != self._current_dataset:
                with self._lock:
                    old_dataset = self._current_dataset
                    self._current_dataset = new_dataset
                if old_dataset:
                    old_dataset.close()

    def start(self) -> None:
        if self._reloader_thread:
            raise ToolchainAssertion("Reload thread already started")
        if self._period_secs > 0:
            _logger.info(f"start reload thread for {self._db_name}")
            self._reloader_thread = Thread(target=self._update_loop, name=f"{self._db_name}-reloader", daemon=True)
            self._reloader_thread.start()

    @contextmanager
    def get(self) -> Iterator[Dataset]:
        """Return the current underlying dataset."""
        with self._lock:
            # We initialize lazily so that we don't do heavyweight work in settings initialization.
            # This has the advantage of not loading the dataset in the gunicorn or runserver parent processes,
            # where it isn't needed.
            if self._current_dataset is None:
                self._current_dataset = self._check_for_update("request")
            yield self._current_dataset

    def stop(self) -> None:
        self._stop = True
