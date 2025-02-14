# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import boto3
import pytest
from moto import mock_dynamodb

from toolchain.aws.dynamodb import DynamoDBTable, ValuesConverter
from toolchain.base.toolchain_error import ToolchainAssertion

_REGION = "ap-northeast-2"
_TABLE_NAME = "seinfeld-nbc"


class TableDef:
    CAPACITY = 1
    LSI_NAME = "lsi_jerry"
    GSI_NAME = "gsi_newman"

    KEY_COLS = {"newman_partition_1", "newman_partition_2", "newman_id", "newman_timestamp"}
    ATTRIBUTES = [
        {"AttributeName": "newman_partition_1", "AttributeType": "S"},
        {"AttributeName": "newman_partition_2", "AttributeType": "S"},
        {"AttributeName": "newman_id", "AttributeType": "S"},
        {"AttributeName": "newman_timestamp", "AttributeType": "N"},
    ]
    KEY_SCHEMA = [
        {"AttributeName": "newman_partition_1", "KeyType": "HASH"},
        {"AttributeName": "newman_id", "KeyType": "RANGE"},
    ]

    LSI = {
        "IndexName": LSI_NAME,
        "Projection": {"ProjectionType": "ALL"},
        "KeySchema": [
            {"AttributeName": "newman_partition_1", "KeyType": "HASH"},
            {"AttributeName": "newman_timestamp", "KeyType": "RANGE"},
        ],
    }
    GSI = {
        "IndexName": GSI_NAME,
        "Projection": {"ProjectionType": "ALL"},
        "KeySchema": [
            {"AttributeName": "newman_partition_2", "KeyType": "HASH"},
            {"AttributeName": "newman_timestamp", "KeyType": "RANGE"},
        ],
    }
    STREAM_SPEC = {"StreamEnabled": True, "StreamViewType": "NEW_AND_OLD_IMAGES"}


@pytest.fixture(autouse=True)
def _start_moto():
    with mock_dynamodb():
        yield


@pytest.fixture()
def table() -> DynamoDBTable:
    table = DynamoDBTable(table_name=_TABLE_NAME, key_columns=TableDef.KEY_COLS, region=_REGION)
    table.create_table_if_not_exists(TableDef)
    assert _get_table_items() == []
    return table


def _get_table_items():
    client = boto3.client("dynamodb", region_name=_REGION)
    return client.scan(TableName=_TABLE_NAME)["Items"]


def test_create_table() -> None:
    table = DynamoDBTable(table_name="seinfeld", key_columns=TableDef.KEY_COLS, region=_REGION)
    table.create_table_if_not_exists(TableDef)
    assert boto3.client("dynamodb", region_name=_REGION).list_tables()["TableNames"] == ["seinfeld"]


def test_put_item(table: DynamoDBTable) -> None:
    record = {"newman_partition_1": "soup", "newman_partition_2": "pool", "newman_id": "crazy", "newman_timestamp": 921}
    table.put_item(record, None)
    assert len(_get_table_items()) == 1


@pytest.mark.xfail(
    reason="Not supported, see https://github.com/spulec/moto/blob/1db617a5309d2ac2fa3e6adc9fb3b90ed43c810a/moto/dynamodb2/models.py#L365"
)
def test_update_item_no_map(table):
    record = {"newman_partition_1": "soup", "newman_partition_2": "pool", "newman_id": "crazy", "newman_timestamp": 921}
    table.put_item(record, None)
    episodes = {"strongbox": (3, {"cast": ["jerry", "george"], "director": "andy ackerman", "length": 22})}
    updated = table.update_dict_in_item(
        key={"newman_partition_1": "soup", "newman_id": "crazy"}, map_name="episodes", update_items=episodes
    )
    assert updated is True
    items = _get_table_items()
    assert len(items) == 1
    assert ValuesConverter().parse_record(items[0]) == {
        "newman_partition_1": "soup",
        "newman_partition_2": "pool",
        "newman_id": "crazy",
        "newman_timestamp": 921,
        "episodes": {"cast": ["jerry", "george"], "director": "andy ackerman", "length": 22},
    }


def test_update_item_empty_map(table: DynamoDBTable) -> None:
    record = {
        "newman_partition_1": "soup",
        "newman_partition_2": "pool",
        "newman_id": "crazy",
        "newman_timestamp": 921,
        "episodes": {},
    }
    table.put_item(record, None)
    episodes = {"strongbox": (3, {"cast": ["jerry", "george"], "director": "andy ackerman", "length": 22})}
    updated = table.update_dict_in_item(
        key={"newman_partition_1": "soup", "newman_id": "crazy"}, map_name="episodes", update_items=episodes
    )
    assert updated is True
    items = _get_table_items()
    assert len(items) == 1
    assert ValuesConverter().parse_record(items[0]) == {
        "newman_partition_1": "soup",
        "newman_partition_2": "pool",
        "newman_id": "crazy",
        "newman_timestamp": 921.0,
        "episodes": {"strongbox": {"cast": ["jerry", "george"], "director": "andy ackerman", "length": 22.0}},
    }


def test_update_item_existing_with_new_version(table: DynamoDBTable) -> None:
    record = {
        "newman_partition_1": "soup",
        "newman_partition_2": "pool",
        "newman_id": "crazy",
        "newman_timestamp": 921,
        "episodes": {"strongbox": {"version": 2, "cast": ["elaine", "kerry"], "director": "unknown", "length": 12}},
    }
    table.put_item(record, None)
    episodes = {"strongbox": (3, {"cast": ["jerry", "george"], "director": "andy ackerman", "length": 22})}
    updated = table.update_dict_in_item(
        key={"newman_partition_1": "soup", "newman_id": "crazy"}, map_name="episodes", update_items=episodes
    )
    assert updated is True
    items = _get_table_items()
    assert len(items) == 1
    assert ValuesConverter().parse_record(items[0]) == {
        "newman_partition_1": "soup",
        "newman_partition_2": "pool",
        "newman_id": "crazy",
        "newman_timestamp": 921.0,
        "episodes": {"strongbox": {"cast": ["jerry", "george"], "director": "andy ackerman", "length": 22.0}},
    }


def test_update_item_existing_with_older_version(table: DynamoDBTable) -> None:
    record = {
        "newman_partition_1": "cup",
        "newman_partition_2": "pool",
        "newman_id": "crazy",
        "newman_timestamp": 921,
        "episodes": {"strongbox": {"version": 8, "cast": ["elaine", "kerry"], "director": "unknown", "length": 12}},
    }
    table.put_item(record, None)
    episodes = {"strongbox": (3, {"cast": ["jerry", "george"], "director": "andy ackerman", "length": 22})}
    updated = table.update_dict_in_item(
        key={"newman_partition_1": "cup", "newman_id": "crazy"}, map_name="episodes", update_items=episodes
    )
    assert updated is False
    items = _get_table_items()
    assert len(items) == 1
    loaded_item = ValuesConverter().parse_record(items[0])
    assert (
        loaded_item
        == record
        == {
            "newman_partition_1": "cup",
            "newman_partition_2": "pool",
            "newman_id": "crazy",
            "newman_timestamp": 921.0,
            "episodes": {"strongbox": {"version": 8, "cast": ["elaine", "kerry"], "director": "unknown", "length": 12}},
        }
    )


def _insert_items(table: DynamoDBTable, count: int) -> list[dict]:
    keys = []
    for i in range(count):
        record = {
            "newman_partition_1": "soup",
            "newman_partition_2": "pool",
            "newman_id": f"crazy-{i+2}",
            "newman_timestamp": 98821,
        }
        keys.append({"newman_partition_1": "soup", "newman_id": f"crazy-{i+2}"})
        table.put_item(record, None)
    return keys


def test_batch_delete_items(table: DynamoDBTable) -> None:
    keys = _insert_items(table, 12)
    assert len(_get_table_items()) == 12
    table.batch_delete_items(keys[7:10])
    assert len(_get_table_items()) == 9


def test_batch_delete_items_over_limit(table: DynamoDBTable) -> None:
    keys = _insert_items(table, 40)
    assert len(_get_table_items()) == 40
    with pytest.raises(ToolchainAssertion, match="Maximum number of items exceeded"):
        table.batch_delete_items(keys[10:])
    assert len(_get_table_items()) == 40
