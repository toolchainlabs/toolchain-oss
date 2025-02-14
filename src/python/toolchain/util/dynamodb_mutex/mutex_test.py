# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime
import time

import pytest
from freezegun import freeze_time
from moto import mock_dynamodb

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainError
from toolchain.util.dynamodb_mutex.mutex import AcquireLockFailedError, DynamoDbMutex, MutexTable


class DummyError(ToolchainError):
    pass


class TestDynamoDbMutex:
    _FAKE_REGION = "ap-northeast-1"

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_dynamodb():
            MutexTable(table_env="test", aws_region=self._FAKE_REGION).create_table()
            yield

    def _get_mutex(self, name, holder, timeout_sec=30):
        return DynamoDbMutex(
            env="test",
            name=name,
            holder=holder,
            aws_region=self._FAKE_REGION,
            timeout=datetime.timedelta(seconds=timeout_sec),
        )

    def test_lock(self):
        mutex = self._get_mutex("no-bagel-no-bagel", "kramer")
        assert mutex.is_locked is False
        assert mutex.lock() is True
        assert mutex.is_locked is True
        assert self._get_mutex("no-bagel-no-bagel", "kramer").is_locked is True

    def test_release(self):
        mutex = self._get_mutex("no-bagel-no-bagel", "kramer")
        same_mutex = self._get_mutex("no-bagel-no-bagel", "kramer")
        different_holder = self._get_mutex("no-bagel-no-bagel", "jerry")
        assert mutex.lock() is True
        assert same_mutex.is_locked is True
        assert different_holder.is_locked is True

        # Other holder can't release
        assert different_holder.release() is False
        assert mutex.is_locked is True
        assert same_mutex.is_locked is True

        # Original holder releases
        assert mutex.release() is True
        assert mutex.is_locked is False
        assert same_mutex.is_locked is False

    def test_lock_expiration(self):
        mutex = self._get_mutex("no-bagel-no-bagel", "kramer")
        with freeze_time(utcnow() - datetime.timedelta(minutes=3)):
            assert mutex.lock() is True
            assert mutex.is_locked is True
        assert mutex.is_locked is False

    def test_mutual_exclusion(self):
        mutex = self._get_mutex("no-bagel-no-bagel", "kramer")
        assert mutex.lock() is True
        assert mutex.lock() is False

    def test_with(self):
        mutex = self._get_mutex("no-bagel-no-bagel", "kramer")
        ft = freeze_time(utcnow() - datetime.timedelta(minutes=3))
        ft.start()
        try:
            with mutex:
                ft.stop()
            raise DummyError("Handling exceptions test")
        except DummyError:
            assert mutex.is_locked is False

    def test_with_fail(self):
        mutex = self._get_mutex("no-bagel-no-bagel", "kramer", timeout_sec=1)
        mutex.lock()
        mutex2 = self._get_mutex("no-bagel-no-bagel", "jerry", timeout_sec=1)
        with pytest.raises(AcquireLockFailedError, match="no-bagel-no-bagel is held by 'kramer'"), mutex2:
            time.sleep(3)
