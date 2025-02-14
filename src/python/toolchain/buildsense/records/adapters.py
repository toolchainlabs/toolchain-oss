# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from dataclasses import fields

from toolchain.buildsense.records.run_info import CIDetails, InvalidRunInfoData, RunInfo, ServerInfo

_RUN_INFO_FIELDS = frozenset(field.name for field in fields(RunInfo))
_logger = logging.getLogger(__name__)

_FORBIDDEN_INPUT_FIELDS = frozenset(("indicators", "modified_fields", "collected_platform_info"))


def from_dynamodb_item(run_info_json: dict) -> RunInfo:
    key = run_info_json.pop("EnvCustomerRepoUser")
    del run_info_json["EnvCustomerRepo"]
    del run_info_json["Environment"]
    # We use run_timestamp in dynamodb since is a reserved word in dynamodb and cannot be use as a key.
    run_info_json["timestamp"] = run_info_json.pop("run_timestamp")
    # Temporary, until this gets cleaned up from dynamodb.
    run_info_json.pop("target_data", None)
    _remove_new_fields(key, run_info_json)
    return RunInfo.from_json_dict(run_info_json)


def _remove_new_fields(key: str, run_info_json: dict) -> None:
    """remove fields that are not part of RunInfo.

    This logic allows us to add fields to RunInfo without breaking old code that is not aware of those fields.
    """
    extra_fields = set(run_info_json.keys()).difference(_RUN_INFO_FIELDS)
    if extra_fields:
        _logger.warning(f"from_dynamodb_item {key=} drop_fields: {extra_fields}")
        for field in extra_fields:
            del run_info_json[field]


def from_post_data(
    *, run_id: str, run_info_json: dict, repo, user, server_info: ServerInfo, ci_details: CIDetails | None = None
) -> RunInfo:
    run_info_json.update(
        run_id=run_id, user_api_id=user.api_id, customer_id=repo.customer_id, repo_id=repo.pk, server_info=server_info
    )
    invalid_fields = _FORBIDDEN_INPUT_FIELDS.intersection(run_info_json.keys())
    if invalid_fields:
        raise InvalidRunInfoData(f"{', '.join(sorted(invalid_fields))} are server side field")
    del run_info_json["user"]
    run_info_json.pop("target_data", None)
    run_info_json.pop("goals", None)
    del run_info_json["datetime"]
    run_info = RunInfo.from_json_dict(run_info_json)
    run_info.ci_info = ci_details
    return run_info


def to_elasticsearch_document(run_info: RunInfo) -> dict:
    run_info_json = run_info.to_json_dict()
    # Not indexing to ES.
    del run_info_json["indicators"]
    del run_info_json["modified_fields"]
    del run_info_json["collected_platform_info"]
    return run_info_json
