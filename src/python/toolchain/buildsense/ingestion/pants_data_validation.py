# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from copy import deepcopy

_logger = logging.getLogger(__name__)


class RunInfoValidator:
    _MAX_SPECS = 10
    _MAX_SPEC_SIZE = 128
    _MAX_CMD_LINE = 1024

    def __init__(self, validate: bool) -> None:
        self._validate = validate

    def sanitize_and_validate_run_info(self, run_id: str, run_info_json: dict) -> tuple[list[str], dict]:
        # for now we only sanitize which we have to do to avoid downstream errors (in dynamodb)
        # We still need to add some more data validation that initially will be optional
        # To check that fields various fields look like something expected.s
        return self._sanitize_run_info(run_id, run_info_json)

    def _sanitize_run_info(self, run_id: str, run_info_json: dict) -> tuple[list[str], dict]:
        # Doing some tricks here to avoid copying run_info_json, in most cases we won't modify run_info_json so copying it is wasteful.
        # if we need to change it then we copy it, but there is logic here (using the `copied` arg) to make sure we only copy once even if we end up making multiple changes.
        # This is because modifying the "original" run_info_json will modify the data we end up storing in s3 which is not desirable.
        # we want to data we save into s3 to be as raw (i.e. what we got over the network) as possible.
        trimmed: list[str] = []
        run_info_json, copied_1 = self._maybe_trim_str(
            run_info_json, "cmd_line", self._MAX_CMD_LINE, trimmed, copied=False
        )
        run_info_json, _ = self._maybe_trim_list(
            run_info_json,
            "specs_from_command_line",
            max_item_length=self._MAX_SPEC_SIZE,
            max_items=self._MAX_SPECS,
            trimmed=trimmed,
            copied=copied_1,
        )
        if trimmed:
            _logger.warning(f"{run_id=} sanitized: {trimmed}")
        return trimmed, run_info_json

    def _maybe_trim_list(
        self,
        run_info_json: dict,
        field: str,
        max_item_length: int,
        max_items: int,
        trimmed: list[str],
        copied: bool,
    ) -> tuple[dict, bool]:
        was_trimmed = False
        items = run_info_json[field]
        if len(items) > max_items:
            items = items[:max_items]
            was_trimmed = True
        updated_items = []
        for item in items:
            if len(item) > max_item_length:
                item = item[:max_item_length]
                was_trimmed = True
            updated_items.append(item)
        if not was_trimmed:
            return run_info_json, False
        trimmed.append(field)
        return self._update_run_info_json(run_info_json, copied, field=field, new_value=updated_items), True

    def _maybe_trim_str(
        self, run_info_json: dict, field: str, max_length: int, trimmed: list[str], copied: bool
    ) -> tuple[dict, bool]:
        value = run_info_json[field]
        if len(value) < max_length:
            return run_info_json, False
        trimmed.append(field)
        return self._update_run_info_json(run_info_json, copied, field=field, new_value=value[:max_length]), True

    def _update_run_info_json(self, run_info_json: dict, copied: bool, field: str, new_value) -> dict:
        if not copied:
            run_info_json = deepcopy(run_info_json)
        run_info_json[field] = new_value
        return run_info_json
