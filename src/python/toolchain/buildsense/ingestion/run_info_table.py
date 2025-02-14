# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import base64
import datetime
import json
import logging
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any

from django.conf import settings

from toolchain.aws.dynamodb import DynamoDBTable
from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import InvalidCursorError, ToolchainAssertion
from toolchain.buildsense.records.adapters import from_dynamodb_item
from toolchain.buildsense.records.run_info import RunInfo, RunKey, WorkUnit

_logger = logging.getLogger(__name__)


class TableDef:
    CAPACITY = 1
    LSI_NAME = "UserRuns"
    GSI_NAME = "RepoRuns"
    LSI_EXPRESSION = "EnvCustomerRepoUser = :partition_key AND run_timestamp BETWEEN :earliest AND :latest"
    GSI_EXPRESSION = "EnvCustomerRepo = :partition_key AND run_timestamp BETWEEN :earliest AND :latest"
    UPDATE_TIMESTAMP_EXPRESSION = "SET server_info.accept_time = :last_update"
    UPDATE_NOT_FINAL_EXPRESSION = (
        "attribute_exists(EnvCustomerRepoUser) AND attribute_exists(run_id) AND outcome = :allowed_update_outcome"
    )
    AVOID_OVERWRITE_EXPRESSION = "attribute_not_exists(EnvCustomerRepoUser) AND attribute_not_exists(run_id)"
    ALLOW_OVERWRITE_NON_FINAL = "attribute_not_exists(EnvCustomerRepoUser) OR outcome = :allowed_update_outcome"
    ALLOWED_OUTCOME_VALUES = {":allowed_update_outcome": "NOT_AVAILABLE"}
    KEY_COLS = {"EnvCustomerRepo", "EnvCustomerRepoUser", "run_id", "run_timestamp"}
    ATTRIBUTES = [
        {"AttributeName": "EnvCustomerRepoUser", "AttributeType": "S"},
        {"AttributeName": "EnvCustomerRepo", "AttributeType": "S"},
        {"AttributeName": "run_id", "AttributeType": "S"},
        {"AttributeName": "run_timestamp", "AttributeType": "N"},
    ]
    KEY_SCHEMA = [
        {"AttributeName": "EnvCustomerRepoUser", "KeyType": "HASH"},
        {"AttributeName": "run_id", "KeyType": "RANGE"},
    ]
    LSI = {
        "IndexName": LSI_NAME,
        "Projection": {"ProjectionType": "ALL"},
        "KeySchema": [
            {"AttributeName": "EnvCustomerRepoUser", "KeyType": "HASH"},
            {"AttributeName": "run_timestamp", "KeyType": "RANGE"},
        ],
    }
    GSI = {
        "IndexName": GSI_NAME,
        "Projection": {"ProjectionType": "ALL"},
        "KeySchema": [
            {"AttributeName": "EnvCustomerRepo", "KeyType": "HASH"},
            {"AttributeName": "run_timestamp", "KeyType": "RANGE"},
        ],
    }
    STREAM_SPEC = {"StreamEnabled": True, "StreamViewType": "NEW_AND_OLD_IMAGES"}


@dataclass(frozen=True)
class TableResultsPage:
    results: tuple[RunInfo, ...]
    cursor: str | None
    count: int


class RunInfoTable:
    _table = None

    # Only retrieve builds from the last 3 days by default.
    _DEFAULT_QUERY_TIMEDELTA = datetime.timedelta(days=3)

    @classmethod
    def for_customer_id(cls, customer_id: str, allow_overwrites: bool = False):
        return cls(customer_id, allow_overwrites)

    def __init__(self, customer_id: str, allow_overwrites: bool) -> None:
        self._env = settings.TOOLCHAIN_ENV.get_env_name()
        self._customer_id = customer_id
        self._allow_overwrites = allow_overwrites

    def __str__(self) -> str:
        return f"RunInfoTable(customer_id={self._customer_id} environment={self._env})"

    @classmethod
    def create_table(cls) -> None:
        table = cls._get_table()
        table.create_table_if_not_exists(TableDef)

    @classmethod
    def _get_table(cls) -> DynamoDBTable:
        if not cls._table:
            cls._table = DynamoDBTable(table_name=settings.RUN_INFO_DYNAMODB_TABLE_NAME, key_columns=TableDef.KEY_COLS)
        return cls._table

    def _get_user_partition_info(self, repo_id: str, user_api_id: str) -> tuple[str, str]:
        if not repo_id or not user_api_id:
            raise ToolchainAssertion("Invalid values")
        return "EnvCustomerRepoUser", f"{self._env}:{self._customer_id}:{repo_id}:{user_api_id}"

    def _get_repo_partition_info(self, repo_id: str) -> tuple[str, str]:
        if not repo_id:
            raise ToolchainAssertion("Invalid repo id")
        return "EnvCustomerRepo", f"{self._env}:{self._customer_id}:{repo_id}"

    def check_access(self, repo) -> dict:
        results = self.get_repo_builds(
            repo_id=repo.pk, earliest=datetime.datetime(2019, 1, 1, tzinfo=datetime.timezone.utc), limit=1
        )
        return {"run_info_table": results.count}

    def get_by_run_id(self, *, repo_id: str, user_api_id: str, run_id: str) -> RunInfo | None:
        if not run_id:
            raise ToolchainAssertion("run_id can't be empty")
        partition_key, partition_value = self._get_user_partition_info(repo_id, user_api_id)
        key = {partition_key: partition_value, "run_id": run_id}
        table = self._get_table()
        item = table.get_item(key)
        return from_dynamodb_item(item) if item else None

    def get_by_run_ids(self, run_keys: Sequence[RunKey], repo_id=None) -> tuple[RunInfo, ...]:
        if not run_keys:
            raise ToolchainAssertion("Empty RunKeys")
        keys = []
        ordered_run_ids = []
        for run_key in run_keys:
            ordered_run_ids.append(run_key.run_id)
            partition_key, partition_value = self._get_user_partition_info(
                repo_id or run_key.repo_id, run_key.user_api_id
            )
            keys.append({partition_key: partition_value, "run_id": run_key.run_id})
        table = self._get_table()
        items = table.batch_get_items(keys)
        return tuple(
            from_dynamodb_item(item) for item in sorted(items, key=lambda item: ordered_run_ids.index(item["run_id"]))
        )

    def update_or_insert_run(self, run_info: RunInfo) -> bool:
        # right now this will call put_item and override the row, this is fine for now.
        # But after we start adding the workunit ingestion and storage into the table, this (final) update will need
        # to be more granular.
        return self._put_run_info(
            run_info=run_info,
            expression=TableDef.ALLOW_OVERWRITE_NON_FINAL,
            expression_values=TableDef.ALLOWED_OUTCOME_VALUES,
        )

    def save_run(self, run_info: RunInfo) -> bool:
        expression = "" if self._allow_overwrites else TableDef.AVOID_OVERWRITE_EXPRESSION
        return self._put_run_info(run_info=run_info, expression=expression, expression_values={})

    def _put_run_info(self, run_info: RunInfo, expression: str, expression_values: dict) -> bool:
        partition_key, partition_value = self._get_user_partition_info(run_info.repo_id, run_info.user_api_id)
        gsi_key, gsi_value = self._get_repo_partition_info(run_info.repo_id)
        record = run_info.to_json_dict()
        timestamp = record.pop("timestamp")
        record.update(
            {
                partition_key: partition_value,
                gsi_key: gsi_value,
                "Environment": self._env,
                "run_timestamp": int(timestamp),
            }
        )
        table = self._get_table()
        return table.put_item(record=record, expression=expression, expression_values=expression_values)

    def update_workunits(
        self, *, repo_id: str, user_api_id: str, run_id: str, last_update: datetime.datetime, workunits: list[WorkUnit]
    ) -> bool:
        partition_key, partition_value = self._get_user_partition_info(repo_id, user_api_id)
        key = {partition_key: partition_value, "run_id": run_id}
        table = self._get_table()
        values: dict[str, Any] = {":last_update": last_update.timestamp()}
        values.update(TableDef.ALLOWED_OUTCOME_VALUES)
        return table.update_item(
            key=key,
            condition_expression=TableDef.UPDATE_NOT_FINAL_EXPRESSION,
            update_expression=TableDef.UPDATE_TIMESTAMP_EXPRESSION,
            expression_values=values,
        )

        # TODO: chunks ?
        # update_items = {unit.workunit_id: (unit.version, unit.to_json_dict()) for unit in workunits}
        # For now the data we get from pants is not complete, there is some essential stuff we want to have there.
        # so we go thru the process of passing it alone but not writing it.
        # return table.update_dict_in_item(key=key, map_name="work_units", update_items=update_items)
        # return bool(update_items)

    def _parse_cursor(self, cursor: str | None, *required_keys: str) -> dict | None:
        if not cursor:
            return None
        try:
            last_key_dict = json.loads(base64.b64decode(cursor))
        except ValueError:
            raise InvalidCursorError(f"Failed to decode cursor={cursor}")
        if not isinstance(last_key_dict, dict):
            raise InvalidCursorError(f"Invalid json in cursor {last_key_dict}")

        expected = {"run_id", "run_timestamp"}
        expected.update(required_keys)
        if expected != set(last_key_dict.keys()):
            raise InvalidCursorError(f"Invalid or missing keys in cursor: {last_key_dict} {expected=}")
        if not all(isinstance(val, (str, float)) for val in last_key_dict.values()):
            raise InvalidCursorError(f"Invalid values in cursor: {last_key_dict}")
        return last_key_dict

    def get_user_repo_builds(
        self,
        *,
        repo_id: str,
        user_api_id: str,
        earliest: datetime.datetime | None = None,
        latest: datetime.datetime | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> TableResultsPage:
        partition_key, partition_value = self._get_user_partition_info(repo_id, user_api_id)
        last_key_dict = self._parse_cursor(cursor, partition_key)
        last_key_dict = {partition_key: partition_value, "run_id": last_key_dict["run_id"]} if last_key_dict else None
        items, last_key, count = self._get_builds(
            index_name=TableDef.LSI_NAME,
            expression=TableDef.LSI_EXPRESSION,
            partition_value=partition_value,
            earliest=earliest,
            latest=latest,
            limit=limit,
            last_key=last_key_dict,
        )
        cursor = self._encode_cursor(last_key)
        return TableResultsPage(results=items, cursor=cursor, count=count)

    def _encode_cursor(self, last_key: dict | None) -> str | None:
        if not last_key:
            return None
        return base64.b64encode(json.dumps(last_key).encode()).decode()

    def _parse_repo_builds_cursor(
        self, cursor: str | None, repo_id: str, partition_key: str, partition_value: str
    ) -> dict | None:
        last_key_dict = self._parse_cursor(cursor, "EnvCustomerRepo", "user_api_id")
        if not last_key_dict:
            return None
        main_key, main_value = self._get_user_partition_info(repo_id, last_key_dict.pop("user_api_id"))
        last_key_dict.update({partition_key: partition_value, main_key: main_value})
        run_timestamp = last_key_dict.pop("run_timestamp")
        try:
            last_key_dict["run_timestamp"] = int(float(run_timestamp))
        except ValueError:
            raise InvalidCursorError(f"Invalid run_timestamp: {run_timestamp}")
        return last_key_dict

    def iterate_repo_builds(
        self,
        repo_id: str,
        earliest: datetime.datetime | None = None,
        latest: datetime.datetime | None = None,
        batch_size: int = 50,
    ) -> Iterator[tuple[RunInfo, ...]]:
        cursor = None
        while True:
            result_page = self.get_repo_builds(repo_id=repo_id, earliest=earliest, cursor=cursor, limit=batch_size)
            run_infos = result_page.results
            cursor = result_page.cursor
            if not run_infos:
                break
            yield run_infos
            if not result_page.cursor:
                break

    def get_repo_builds(
        self,
        *,
        repo_id: str,
        earliest: datetime.datetime | None = None,
        latest: datetime.datetime | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> TableResultsPage:
        partition_key, partition_value = self._get_repo_partition_info(repo_id)
        last_key_dict = self._parse_repo_builds_cursor(cursor, repo_id, partition_key, partition_value)
        items, last_key, count = self._get_builds(
            index_name=TableDef.GSI_NAME,
            expression=TableDef.GSI_EXPRESSION,
            partition_value=partition_value,
            earliest=earliest,
            latest=latest,
            limit=limit,
            last_key=last_key_dict,
        )
        if last_key:
            main_key = last_key.pop("EnvCustomerRepoUser")
            last_key["user_api_id"] = main_key[main_key.rfind(":") + 1 :]
            # We only want string values in cursor.
            last_key["run_timestamp"] = str(last_key["run_timestamp"])
            cursor = self._encode_cursor(last_key)
        else:
            cursor = None
        return TableResultsPage(results=items, cursor=cursor, count=count)

    def _get_builds(
        self,
        index_name: str,
        expression: str,
        partition_value: str,
        earliest: datetime.datetime | None,
        latest: datetime.datetime | None,
        limit: int | None,
        last_key: dict | None,
    ) -> tuple[tuple[RunInfo, ...], dict | None, int]:
        table = self._get_table()
        now = utcnow()
        earliest = earliest or (now - self._DEFAULT_QUERY_TIMEDELTA)
        latest = latest or now
        if earliest > latest:
            raise ToolchainAssertion(f"Earliest must be before or equal to latest. earliest={earliest} latest={latest}")
        _logger.debug(f"get_builds for {partition_value} on {index_name} earliest={earliest} latest={latest}")
        values = {
            ":partition_key": partition_value,
            ":earliest": int(earliest.timestamp()),
            ":latest": int(latest.timestamp()),
        }
        results = table.query(
            index_name=index_name, expression=expression, expression_values=values, limit=limit, last_key=last_key
        )

        runs = tuple(from_dynamodb_item(ri) for ri in results.items)
        return runs, results.last_key, results.count

    def delete_build(self, *, repo_id: str, user_api_id: str, run_id: str) -> None:
        if not run_id:
            raise ToolchainAssertion("run_id can't be empty")
        partition_key, partition_value = self._get_user_partition_info(repo_id, user_api_id)
        key = {partition_key: partition_value, "run_id": run_id}
        table = self._get_table()
        table.delete_item(key)

    def delete_builds(self, run_keys: Sequence[RunKey]) -> None:
        if not run_keys:
            raise ToolchainAssertion("Empty RunKeys")
        keys = []
        for run_key in run_keys:
            partition_key, partition_value = self._get_user_partition_info(run_key.repo_id, run_key.user_api_id)
            keys.append({partition_key: partition_value, "run_id": run_key.run_id})
        table = self._get_table()
        table.batch_delete_items(keys)
