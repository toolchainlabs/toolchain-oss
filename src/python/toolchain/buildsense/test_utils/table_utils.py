# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from moto.core import DEFAULT_ACCOUNT_ID
from moto.dynamodb.models import dynamodb_backends


def get_table_items() -> list[dict]:
    items_by_hash_key = dynamodb_backends[DEFAULT_ACCOUNT_ID]["ap-northeast-1"].tables["test-runinfo-v1"].items
    items = []
    for values_for_hash_key in items_by_hash_key.values():
        items.extend(values_for_hash_key.values())
    return items


def get_table_items_count() -> int:
    return len(get_table_items())
