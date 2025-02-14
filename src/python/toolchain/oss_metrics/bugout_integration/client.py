# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging

from bugout.app import Bugout
from bugout.exceptions import BugoutResponseException
from django.conf import settings

from toolchain.base.toolchain_error import ToolchainError

_logger = logging.getLogger(__name__)


class TransientBugoutError(ToolchainError):
    pass


class BugoutClient:
    PAGE_SIZE = 500  # https://github.com/bugout-dev/humbug/blob/57607cd2d205ff5eff1d1caafdc99585cf0afe04/scripts/humbug.bash#L32

    @classmethod
    def for_django_settings(cls, journal_id: str) -> BugoutClient:
        return cls.create(secrets_reader=settings.SECRETS_READER, journal_id=journal_id)

    @classmethod
    def create(cls, secrets_reader, journal_id: str) -> BugoutClient:
        token = secrets_reader.get_json_secret_or_raise("bugout-api-key")["api-key"]
        return cls(token, journal_id)

    def __init__(self, token: str, journal_id: str) -> None:
        self._client = Bugout()
        self._token = token
        self._journal_id = journal_id

    def get_entries(self, *, from_datetime: datetime.datetime, to_datetime: datetime.datetime) -> list[dict]:
        # https://github.com/bugout-dev/humbug/blob/main/scripts/humbug.bash
        items: list[dict] = []
        offset = 0
        # Filters is an undocumented feature. `{created_at|updated_at}:{<|<=|>|>=}<epoch time>`
        # this is based on https://bugout-dev.slack.com/archives/C017DTE72CQ/p1640903162012800
        search_filters = [
            f"created_at:>={int(from_datetime.timestamp())}",
            f"created_at:<{int(to_datetime.timestamp())}",
        ]
        while True:
            try:
                results_page = self._client.search(
                    token=self._token,
                    journal_id=self._journal_id,
                    filters=search_filters,
                    offset=offset,
                    limit=self.PAGE_SIZE,
                    query="order=asc",
                    timeout=60,
                )
            except BugoutResponseException as error:
                _logger.warning(f"Failed to search bugout: {search_filters=} {offset=} {error!r}")
                raise TransientBugoutError(repr(error))
            _logger.info(
                f"bugout_get_entries {offset=} (from_datetime={from_datetime.isoformat()}, to_datetime={to_datetime.isoformat()}): entries={len(results_page.results)} total={results_page.total_results} next_offset={results_page.next_offset} "
            )
            items.extend(item.dict() for item in results_page.results)
            if not results_page.next_offset:
                break
            offset = results_page.next_offset
        return items
