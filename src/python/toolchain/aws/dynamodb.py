# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

import botocore
from boto3.dynamodb.types import DYNAMODB_CONTEXT
from boto3.dynamodb.types import TypeDeserializer as Boto3TypeDeserializer
from boto3.dynamodb.types import TypeSerializer as Boto3TypeSerializer

from toolchain.aws.aws_api import AWSService
from toolchain.base.toolchain_error import ToolchainAssertion

logger = logging.getLogger(__name__)


class DynamoDB(AWSService):
    service = "dynamodb"


class TypeSerializer(Boto3TypeSerializer):
    # The boto3 serializer just blows up (ValueError) if it sees a float.
    def __init__(self, float_quantize: str = ".000001") -> None:
        super().__init__()
        self._float_quantize = Decimal(float_quantize)

    def _is_number(self, value):
        return isinstance(value, (int, float, Decimal))

    def _serialize_n(self, value):
        if isinstance(value, float):
            value = Decimal(value).quantize(self._float_quantize)
        number = str(DYNAMODB_CONTEXT.create_decimal(value))
        if number in ["Infinity", "NaN"]:
            raise TypeError("Infinity and NaN not supported")
        return number

    # DynamoDB doesn't allow empty strings
    def _is_null(self, value):
        return value in [None, ""]


class TypeDeserializer(Boto3TypeDeserializer):
    def _deserialize_n(self, value):
        decimal = super()._deserialize_n(value)
        return float(decimal)


class ValuesConverter:
    def __init__(self) -> None:
        self._serializer = TypeSerializer()
        self._deserializer = TypeDeserializer()

    def parse_record(self, record):
        converted = {}
        for key, value in record.items():
            val = self._deserializer.deserialize(value)
            converted[int(key) if key.isdigit() else key] = val
        return converted

    def convert_item(self, item):
        return {str(key): self._serializer.serialize(value) for key, value in item.items()}


class DynamoDBTable:
    DEFAULT_QUERY_LIMIT = 30

    @dataclass
    class QueryResults:
        items: list[dict]
        last_key: dict | None
        count: int

    def __init__(self, *, table_name: str, key_columns: Iterable[str], region: str | None = None):
        self._client = DynamoDB(region).client
        self._table_name = table_name
        self._key_cols = set(key_columns)
        self._converter = ValuesConverter()

    def __str__(self):
        return f"DynamoDBTable(table_name={self._table_name}"

    def create_table_if_not_exists(self, table_def):
        table_name = self._table_name
        if table_name in self._client.list_tables()["TableNames"]:
            logger.warning(f"Table {table_name} already exists.")
            return
        capacity = table_def.CAPACITY
        pv = {"ReadCapacityUnits": capacity, "WriteCapacityUnits": capacity}
        if table_def.GSI:
            gsi = [dict(table_def.GSI)]
            gsi[0]["ProvisionedThroughput"] = pv
        else:
            gsi = []
        logger.info(f"Creating table {table_name}")
        extra_kwargs = dict(
            LocalSecondaryIndexes=[table_def.LSI] if table_def.LSI else [],
            GlobalSecondaryIndexes=gsi,
            StreamSpecification=table_def.STREAM_SPEC if table_def.STREAM_SPEC else None,
        )
        extra_kwargs = {k: v for k, v in extra_kwargs.items() if v}
        self._client.create_table(
            TableName=table_name,
            KeySchema=table_def.KEY_SCHEMA,
            AttributeDefinitions=table_def.ATTRIBUTES,
            ProvisionedThroughput=pv,
            **extra_kwargs,
        )

    def get_item(self, key: dict) -> dict | None:
        item_key = self._converter.convert_item(key)
        item_response = self._client.get_item(TableName=self._table_name, Key=item_key)
        item = item_response.get("Item")
        return self._converter.parse_record(item) if item else None

    def batch_get_items(self, keys: list[dict]) -> list[dict]:
        item_keys = [self._converter.convert_item(key) for key in keys]
        req_items = {self._table_name: {"Keys": item_keys}}
        items_response = self._client.batch_get_item(RequestItems=req_items)
        items = items_response["Responses"].get(self._table_name, [])
        return [self._converter.parse_record(item) for item in items]

    def query(
        self,
        *,
        index_name: str,
        expression: str,
        expression_values: dict,
        limit: int | None = None,
        last_key: dict | None = None,
    ) -> DynamoDBTable.QueryResults:
        limit = limit or self.DEFAULT_QUERY_LIMIT
        attr_values = self._converter.convert_item(expression_values)
        # We can't pass ExclusiveStartKey=None to boto, it doesn't like it.
        kwargs = {"ExclusiveStartKey": self._converter.convert_item(last_key)} if last_key else {}
        resp = self._client.query(
            TableName=self._table_name,
            IndexName=index_name,
            ScanIndexForward=False,  # Descending order
            Limit=limit,
            Select="ALL_ATTRIBUTES",
            KeyConditionExpression=expression,
            ExpressionAttributeValues=attr_values,
            **kwargs,
        )
        last_key = resp.get("LastEvaluatedKey") or None
        if last_key:
            last_key = self._converter.parse_record(last_key)
        items = [self._converter.parse_record(item) for item in resp["Items"]]
        return self.QueryResults(items=items, last_key=last_key, count=resp["Count"])

    def _is_conditional_check_fail(self, error: botocore.exceptions.ClientError) -> bool:
        # a ConditionalCheckFailedException is raised when the DynamoDB "fails" to put the item
        # because the ConditionExpression evaluation fails.
        # This is expected and we use this to prevent overwrites.
        return error.response["Error"]["Code"] == "ConditionalCheckFailedException"

    def update_item(
        self, key: dict, condition_expression: str, update_expression: str, expression_values: dict
    ) -> bool:
        item_key = self._converter.convert_item(key)
        expression_attrs = self._converter.convert_item(expression_values)
        try:
            self._client.update_item(
                TableName=self._table_name,
                Key=item_key,
                UpdateExpression=update_expression,
                ConditionExpression=condition_expression,
                ExpressionAttributeValues=expression_attrs,
            )
        except botocore.exceptions.ClientError as error:
            if not self._is_conditional_check_fail(error):
                raise
            return False
        return True

    def put_item(self, record: dict, expression: str | None, expression_values: dict | None = None) -> bool:
        if not self._key_cols.issubset(set(record.keys())):
            raise ToolchainAssertion(f"Missing key column(s) {record}")
        item = self._converter.convert_item(record)
        # We can't pass ConditionExpression=None to boto, it doesn't like it.
        if expression:
            kwargs = {"ConditionExpression": expression}
            if expression_values:
                kwargs.update(ExpressionAttributeValues=self._converter.convert_item(expression_values))
        else:
            kwargs = {}
        try:
            self._client.put_item(TableName=self._table_name, Item=item, **kwargs)
        except botocore.exceptions.ClientError as error:
            if not self._is_conditional_check_fail(error):
                raise
            return False
        return True
        # TODO: report to Prometheus. https://github.com/toolchainlabs/toolchain/issues/1023

    def update_dict_in_item(self, key: dict, map_name, update_items: dict[str, tuple[int, dict]]) -> bool:
        if not update_items:
            raise ToolchainAssertion("update_items can't be empty.")
        item_key = self._converter.convert_item(key)
        update_parts = []
        condition_parts = []
        values = {}
        for item_id, (version, item) in update_items.items():
            item_key_path = f"{map_name}.{item_id}"
            item_id_var_name = f":item_{item_id}"
            item_ver_var_name = f":version_{item_id}"
            update_parts.append(f"{item_key_path} = {item_id_var_name}")
            condition_parts.append(
                f"(attribute_not_exists({item_key_path}) OR {item_key_path}.version < {item_ver_var_name})"
            )
            values.update(
                {item_id_var_name: {"M": self._converter.convert_item(item)}, item_ver_var_name: {"N": str(version)}}
            )

        parts_str = ", ".join(update_parts)
        try:
            self._client.update_item(
                TableName=self._table_name,
                Key=item_key,
                UpdateExpression=f"SET {parts_str}",
                ConditionExpression=" AND ".join(condition_parts),
                ExpressionAttributeValues=values,
            )
        except botocore.exceptions.ClientError as error:
            if not self._is_conditional_check_fail(error):
                raise
            return False
        return True

    def delete_item(self, key: dict) -> None:
        item_key = self._converter.convert_item(key)
        self._client.delete_item(TableName=self._table_name, Key=item_key)

    def batch_delete_items(self, keys: list[dict]) -> None:
        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/dynamodb.html#DynamoDB.Client.batch_write_item
        if len(keys) > 25:
            # This is enforced on thw AWS side, so we want to avoid calls that will fail.
            # see https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_BatchWriteItem.html
            raise ToolchainAssertion(f"Maximum number of items exceeded: {len(keys)}")
        requests = [{"DeleteRequest": {"Key": self._converter.convert_item(key)}} for key in keys]
        response = self._client.batch_write_item(
            RequestItems={self._table_name: requests},
            ReturnConsumedCapacity="TOTAL",
            ReturnItemCollectionMetrics="SIZE",
        )
        logger.info(f"batch_delete_items {response=}")
