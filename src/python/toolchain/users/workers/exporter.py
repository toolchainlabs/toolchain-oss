# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
import logging

from django.conf import settings

from toolchain.aws.s3 import S3
from toolchain.base.datetime_tools import utcnow
from toolchain.django.site.models import Customer
from toolchain.users.models import (
    PeriodicallyExportCustomers,
    PeriodicallyExportRemoteWorkerTokens,
    RemoteExecWorkerToken,
)
from toolchain.workflow.worker import Worker

_logger = logging.getLogger(__name__)


class PeriodicCustomersExporter(Worker):
    work_unit_payload_cls = PeriodicallyExportCustomers
    # We want do do it during load so the worker container won't start if this is not properly set.
    _EXPORT_BUCKET, _EXPORT_KEY = S3.parse_s3_url(settings.CUSTOMER_EXPORT_S3_URL)

    def do_work(self, work_unit_payload: PeriodicallyExportCustomers) -> bool:
        customers_map = {customer.id: customer.slug for customer in Customer.objects.all()}
        _logger.info(f"Exporting {len(customers_map)} to s3://{self._EXPORT_BUCKET}/{self._EXPORT_KEY}")
        S3().upload_json_str(bucket=self._EXPORT_BUCKET, key=self._EXPORT_KEY, json_str=json.dumps(customers_map))
        if work_unit_payload.period_minutes is None:
            # We were a one-time processing
            return True
        # Note that if we're not a one-time processing we never succeed, but keep scheduling the checker forever.
        return False

    def on_reschedule(self, work_unit_payload: PeriodicallyExportCustomers) -> datetime.datetime:
        return utcnow() + datetime.timedelta(minutes=work_unit_payload.period_minutes)


class PeriodicRemoteWorkerTokensExporter(Worker):
    work_unit_payload_cls = PeriodicallyExportRemoteWorkerTokens
    # We want do do it during load so the worker container won't start if this is not properly set.
    _EXPORT_BUCKET, _EXPORT_KEY = S3.parse_s3_url(settings.REMOTE_WORKERS_TOKENS_EXPORT_S3_URL)
    # Used to cache info in-process/memorty to avoid calling into s3 if we don't need to.
    # This assume that the uploader/exporter is a singleton across our system, which is the case.
    _LAST_TOKEN_UPLOAD: datetime.datetime | None = None

    def _token_to_json(self, worker_token: RemoteExecWorkerToken) -> dict:
        # Used by proxy server, so no backward incompatible changes are allowed.
        return {
            "id": worker_token.id,
            "instance_name": worker_token.customer_id,
            "customer_slug": worker_token.customer_slug,
            "is_active": worker_token.is_active,
        }

    def _export_tokens(self) -> None:
        qs = RemoteExecWorkerToken.get_all_tokens()
        worker_tokens = {worker_token.token: self._token_to_json(worker_token) for worker_token in qs}
        _logger.info(f"Exporting {len(worker_tokens)} tokens to s3://{self._EXPORT_BUCKET}/{self._EXPORT_KEY}")
        S3().upload_json_str(bucket=self._EXPORT_BUCKET, key=self._EXPORT_KEY, json_str=json.dumps(worker_tokens))

    def _get_last_token_upload(cls) -> datetime.datetime | None:
        if cls._LAST_TOKEN_UPLOAD:
            return cls._LAST_TOKEN_UPLOAD
        info = S3().get_info_or_none(bucket=cls._EXPORT_BUCKET, key=cls._EXPORT_KEY)
        if not info:
            return None
        cls._LAST_TOKEN_UPLOAD = info.last_modified
        return cls._LAST_TOKEN_UPLOAD

    def _maybe_export_tokens(self) -> None:
        last_change = RemoteExecWorkerToken.get_last_change_timestamp()
        if not last_change:
            return
        last_upload = self._get_last_token_upload()
        if not last_upload:
            _logger.info("Unkown last upload. exporting tokens")
            self._export_tokens()
            return
        if last_change <= last_upload:
            return
        _logger.info(f"last_change={last_change.isoformat()} last_upload={last_upload.isoformat()}. exporting tokens")
        self._export_tokens()

    def do_work(self, work_unit_payload: PeriodicallyExportRemoteWorkerTokens) -> bool:
        self._maybe_export_tokens()
        if work_unit_payload.period_seconds is None:
            # We were a one-time processing
            return True
        # Note that if we're not a one-time processing we never succeed, but keep scheduling the exporter forever.
        return False

    def on_reschedule(self, work_unit_payload: PeriodicallyExportRemoteWorkerTokens) -> datetime.datetime:
        return utcnow() + datetime.timedelta(seconds=work_unit_payload.period_seconds)
