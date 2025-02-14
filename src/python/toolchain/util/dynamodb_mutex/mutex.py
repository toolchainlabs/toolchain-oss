# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass

from toolchain.aws.dynamodb import DynamoDBTable
from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion, ToolchainError

# Based on https://github.com/chiradeep/dyndb-mutex

_logger = logging.getLogger(__name__)


class AcquireLockFailedError(ToolchainError):
    pass


@dataclass(frozen=True)
class DistLock:
    NO_HOLDER = "__empty__"
    name: str
    holder: str
    expires_at: datetime.datetime

    @classmethod
    def from_dict(cls, data: dict) -> DistLock:
        expiration = datetime.datetime.fromtimestamp(float(data["expire_ts"]), datetime.timezone.utc)
        return cls(name=data["lockname"], holder=data["holder"], expires_at=expiration)

    @property
    def is_held(self) -> bool:
        return self.holder != self.NO_HOLDER


class TableDef:
    CAPACITY = 1
    KEY_COLS = {"lockname"}
    ATTRIBUTES = [{"AttributeName": "lockname", "AttributeType": "S"}]
    KEY_SCHEMA = [{"AttributeName": "lockname", "KeyType": "HASH"}]
    CHECK_HOLDER = "attribute_not_exists(lockname) OR holder = :lock_holder"
    NO_HOLDER_VALUES = {":lock_holder": DistLock.NO_HOLDER}
    PRUNE_EXPIRED = "attribute_not_exists(lockname) OR expire_ts < :now_ts"

    GSI = None
    LSI = None
    STREAM_SPEC = None


def timestamp_millis():
    return int((utcnow() - datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)).total_seconds() * 1000)


class MutexTable:
    def __init__(self, table_env: str, aws_region: str):
        self._table_name = f"mutex-{table_env}"
        self._aws_region = aws_region
        self._row_ttl = datetime.timedelta(hours=6)
        self._table: DynamoDBTable | None = None

    def create_table(self):
        table = self._get_table()
        table.create_table_if_not_exists(TableDef)

    def _get_table(self) -> DynamoDBTable:
        if not self._table:
            self._table = DynamoDBTable(
                table_name=self._table_name, key_columns=TableDef.KEY_COLS, region=self._aws_region
            )
        return self._table

    def _check_holder(self, holder: str) -> None:
        if holder == DistLock.NO_HOLDER or not holder:
            raise ToolchainAssertion("Invalid holder value")

    def write_lock_item(self, lock_name: str, holder: str, timeout: datetime.timedelta) -> bool:
        self._check_holder(holder)
        table = self._get_table()

        expire = utcnow() + timeout
        ttl = expire + self._row_ttl
        record = {
            "lockname": lock_name,
            "expire_ts": int(expire.timestamp()),
            "holder": holder,
            "ttl": int(ttl.timestamp()),
        }
        record_written = table.put_item(
            record=record, expression=TableDef.CHECK_HOLDER, expression_values=TableDef.NO_HOLDER_VALUES
        )
        return record_written

    def _get_cleared_lock(self, lock_name: str) -> dict:
        return {"lockname": lock_name, "expire_ts": 0, "holder": DistLock.NO_HOLDER}

    def clear_lock_item(self, lock_name: str, holder: str) -> bool:
        self._check_holder(holder)
        table = self._get_table()
        record = self._get_cleared_lock(lock_name)
        record_written = table.put_item(
            record=record, expression=TableDef.CHECK_HOLDER, expression_values={":lock_holder": holder}
        )
        return record_written

    def prune_expired(self, lock_name: str, holder: str) -> bool:
        self._check_holder(holder)
        table = self._get_table()
        record = self._get_cleared_lock(lock_name)
        now_ts = int(utcnow().timestamp())
        record_written = table.put_item(
            record=record, expression=TableDef.PRUNE_EXPIRED, expression_values={":now_ts": now_ts}
        )
        return record_written

    def get_lock(self, lock_name: str) -> DistLock | None:
        lock_dict = self._get_table().get_item({"lockname": lock_name})
        return DistLock.from_dict(lock_dict) if lock_dict else None


class DynamoDbMutex:
    def __init__(self, *, env: str, name: str, holder: str, aws_region: str, timeout: datetime.timedelta) -> None:
        self._lockname = name
        self._holder = holder
        self._table = MutexTable(table_env=env, aws_region=aws_region)
        self._timeout = timeout

    def lock(self) -> bool:
        self._table.prune_expired(self._lockname, self._holder)
        return self._table.write_lock_item(lock_name=self._lockname, holder=self._holder, timeout=self._timeout)

    def release(self) -> bool:
        return self._table.clear_lock_item(self._lockname, self._holder)

    def __enter__(self) -> DynamoDbMutex:
        locked = self.lock()
        if not locked:
            lock = self._get_lock()
            holder = lock.holder if lock else "NA"
            raise AcquireLockFailedError(f"{self._lockname} is held by '{holder}'")
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.release()

    @property
    def is_locked(self) -> bool:
        now = utcnow()
        lock = self._get_lock()
        return bool(lock and lock.is_held and lock.expires_at > now)

    def _get_lock(self) -> DistLock | None:
        return self._table.get_lock(self._lockname)

    def __str__(self) -> str:
        return f"DynamoDbMutex(lock_name={self._lockname} holder={self._holder})"

    def __repr__(self) -> str:
        return str(self)
