# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from typing import IO

from django.conf import settings
from prometheus_client import Counter, Histogram

from toolchain.buildsense.ingestion.batched_builds_queue import BatchedBuildsQueue
from toolchain.buildsense.ingestion.errors import BadDataError
from toolchain.buildsense.ingestion.integrations.ci_integration import CIDFullDetails
from toolchain.buildsense.ingestion.integrations.ci_scm_helpers import ScmInfoHelper
from toolchain.buildsense.ingestion.models import ProcessPantsRun, ProcessQueuedBuilds
from toolchain.buildsense.ingestion.pants_data_validation import RunInfoValidator
from toolchain.buildsense.ingestion.run_info_raw_store import RunInfoRawStore
from toolchain.buildsense.ingestion.run_info_table import RunInfoTable
from toolchain.buildsense.ingestion.run_processors.common import (
    RUN_LOGS_ARTIFACTS_CONTENT_TYPE,
    RUN_LOGS_ARTIFACTS_FILE_NAME,
)
from toolchain.buildsense.records.adapters import from_post_data
from toolchain.buildsense.records.run_info import InvalidRunInfoData, RunInfo, ServerInfo
from toolchain.django.site.models import Repo, ToolchainUser

_logger = logging.getLogger(__name__)

BUILDS_SUBMITTED = Counter(
    name="toolchain_buildsense_ingestion_sumbitted_builds",
    documentation="Count submitted builds",
    labelnames=["customer", "repo", "pants_version", "toolchain_plugin_version", "ci"],
)


def _mb_to_kb(*mb_vals: int) -> tuple[int, ...]:
    return tuple(mb * 1024 for mb in mb_vals)


BUILD_SIZE = Histogram(
    name="toolchain_buildsense_ingestion_build_size",
    documentation="Histogram of sumbitted build size (based on request content length).",
    unit="kilobytes",
    labelnames=["customer", "repo", "pants_version", "toolchain_plugin_version", "ci"],
    buckets=(
        *_mb_to_kb(1, 3, 10, 20, 40, 60, 70, 100, 120, 160, 250, 300, 400, 500, 600, 900, 1_100, 1_500),
        float("inf"),
    ),
)


@dataclass(frozen=True)
class RequestContext:
    request_id: str
    accept_time: datetime.datetime
    stats_version: str
    content_length: int | None
    client_ip: str | None = None
    toolchain_plugin_version: str | None = None
    pants_version: str | None = None

    @property
    def normalized_pants_version(self) -> str | None:
        if self.pants_version and "+" in self.pants_version:
            # 2.9.0rc0+gita0a1a7d5 -> 2.9.0rc0
            return self.pants_version.partition("+")[0]
        return self.pants_version


class PantsDataIngestion:
    _ARTIFACT_CONTENT_TYPE = {
        "coverage_raw": "application/octet-stream",
        "coverage_xml": "application/xml",
        "xml_results": "application/xml",
        "stdout": "text/plain",
        "stderr": "text/plain",
    }

    @classmethod
    def for_reprocess_scripts(cls, *, env_name: str, repo: Repo) -> PantsDataIngestion:
        """This entry point is used when migrating data.

        For example, when re-importing data from S3 to DynamoDB. In these cases we set the environment regardles of the
        actual environment. Example use case: see under ingestion/scripts/builds_importer.py.
        """
        return cls(repo=repo, env_name=env_name, allow_overwrites=True, silence_timeouts=False)

    @classmethod
    def for_repo(cls, repo: Repo, validate: bool = True, silence_timeouts: bool = False) -> PantsDataIngestion:
        env_name = settings.TOOLCHAIN_ENV.get_env_name()
        return cls(repo=repo, env_name=env_name, allow_overwrites=False, silence_timeouts=silence_timeouts)

    def __init__(
        self,
        repo: Repo,
        env_name: str,
        allow_overwrites: bool = False,
        validate: bool = True,
        silence_timeouts: bool = False,
    ) -> None:
        self._repo_id = repo.pk
        self._customer_id = repo.customer_id
        self._repo = repo
        self._env_name = env_name
        self._raw_store = RunInfoRawStore.for_repo(repo=repo)
        self._allow_overwrites = allow_overwrites
        self._scm = ScmInfoHelper(customer_id=repo.customer_id, repo_id=repo.pk, silence_timeouts=silence_timeouts)
        self._validator = RunInfoValidator(validate)

    def __str__(self) -> str:
        return f"PantsDataIngestion(environment={self._env_name} repo_id={self._repo.slug})"

    @property
    def _table(self) -> RunInfoTable:
        return RunInfoTable.for_customer_id(self._customer_id, allow_overwrites=self._allow_overwrites)

    def store_build_start(
        self,
        *,
        build_stats: dict,
        user: ToolchainUser,
        request_ctx: RequestContext,
    ) -> tuple[bool, ToolchainUser | None]:
        run_info_json, run_id = self._get_run_info_json(build_stats)
        modified_fields, run_info_json = self._validator.sanitize_and_validate_run_info(run_id, run_info_json)
        ci_full_details, ci_user = self._scm.get_ci_info(
            run_id=run_id, build_stats=build_stats, auth_user=user, ci_user=None
        )
        server_info = self._save_s3_data(
            run_id=run_id,
            is_final=False,
            build_stats=build_stats,
            stats_version=request_ctx.stats_version,
            user=ci_user or user,
            request_id=request_ctx.request_id,
            accept_time=request_ctx.accept_time,
            client_ip=request_ctx.client_ip,
        )
        del run_info_json["id"]
        try:
            run_info = from_post_data(
                run_id=run_id,
                run_info_json=run_info_json,
                repo=self._repo,
                user=ci_user or user,
                server_info=server_info,
                ci_details=ci_full_details.details if ci_full_details else None,
            )
        except InvalidRunInfoData as error:
            # We want a sentry error/alert when this happens
            _logger.exception(f"Invalid data error {error} for {run_id} key={server_info.s3_key}")
            raise BadDataError("Forbidden fields in build data")
        self._update_run_info(run_info=run_info, build_stats=build_stats, modified_fields=modified_fields)
        created = self._table.save_run(run_info)
        _logger.info(
            f"save_build_data s3_key={run_info.server_info.s3_key} run_id={run_info.run_id} timestamp={run_info.timestamp} created={created}"
        )
        return created, ci_user

    def _update_run_info(self, run_info: RunInfo, build_stats: dict, modified_fields: list[str]) -> None:
        run_info.modified_fields = modified_fields
        # We want to also make sure that the platform prop has data (as opposed to just being present and empty)
        run_info.collected_platform_info = bool(build_stats.get("platform"))

    def _get_labels(self, ci: CIDFullDetails | None, request_ctx: RequestContext) -> dict[str, str]:
        return dict(
            customer=self._repo.customer.slug,
            repo=self._repo.slug,
            pants_version=request_ctx.normalized_pants_version or "na",
            toolchain_plugin_version=request_ctx.toolchain_plugin_version or "na",
            ci=ci.ci_system.value if ci else "na",
        )

    def store_build_ended(
        self,
        *,
        build_stats: dict,
        user: ToolchainUser,
        impersonated_user: ToolchainUser | None,
        request_ctx: RequestContext,
        ignore_dups: bool = False,
        build_stats_compressed_file: IO[bytes] | None = None,
    ) -> bool:
        run_info_json, run_id = self._get_run_info_json(build_stats)
        modified_fields, run_info_json = self._validator.sanitize_and_validate_run_info(run_id, run_info_json)
        ci_full_details, ci_user = self._scm.get_ci_info(
            run_id=run_id, build_stats=build_stats, auth_user=user, ci_user=impersonated_user
        )
        server_info = self._save_s3_data(
            run_id=run_id,
            is_final=True,
            build_stats=build_stats,
            user=ci_user or user,
            request_id=request_ctx.request_id,
            accept_time=request_ctx.accept_time,
            stats_version=request_ctx.stats_version,
            ignore_dups=ignore_dups,
            client_ip=request_ctx.client_ip,
            build_stats_compressed_file=build_stats_compressed_file,
        )
        del run_info_json["id"]
        try:
            run_info = from_post_data(
                run_id=run_id,
                run_info_json=run_info_json,
                repo=self._repo,
                user=ci_user or user,
                server_info=server_info,
                ci_details=ci_full_details.details if ci_full_details else None,
            )
        except InvalidRunInfoData as error:
            # We want a sentry error/alert when this happens
            _logger.exception(f"Invalid data error {error} for {run_id} key={server_info.s3_key}")
            raise BadDataError("Forbidden fields in build data")
        self._update_run_info(run_info=run_info, build_stats=build_stats, modified_fields=modified_fields)
        _logger.info(f"Store final build state for {run_info.run_id} outcome={run_info.outcome} user={ci_user or user}")
        created = self._table.update_or_insert_run(run_info)
        labels = self._get_labels(ci=ci_full_details, request_ctx=request_ctx)
        BUILDS_SUBMITTED.labels(**labels).inc()
        if request_ctx.content_length is not None:
            BUILD_SIZE.labels(**labels).observe(int(request_ctx.content_length / 1024))
        if created:
            ProcessPantsRun.create(run_info, repo=self._repo)
        else:
            _logger.warning(f"store_final_build_state not_created for {run_info.run_id}")
        return created

    def _save_s3_data(
        self,
        run_id: str,
        is_final: bool,
        build_stats: dict,
        user: ToolchainUser,
        request_id: str,
        accept_time: datetime.datetime,
        stats_version: str,
        ignore_dups: bool = False,
        client_ip: str | None = None,
        build_stats_compressed_file: IO[bytes] | None = None,
    ) -> ServerInfo:
        if is_final:
            s3_bucket_name, s3_key = self._raw_store.save_final_build_stats(
                run_id=run_id,
                build_stats=build_stats,
                user_api_id=user.api_id,
                ignore_dups=ignore_dups,
                build_stats_compressed_file=build_stats_compressed_file,
            )
        else:
            s3_bucket_name, s3_key = self._raw_store.save_initial_build_stats(
                run_id=run_id, build_stats=build_stats, user_api_id=user.api_id
            )
        if client_ip == "127.0.0.1":
            client_ip = None
        return ServerInfo(
            request_id=request_id,
            accept_time=accept_time,
            stats_version=stats_version,
            environment=self._env_name,
            s3_bucket=s3_bucket_name,
            s3_key=s3_key,
            client_ip=client_ip,
        )

    def _get_run_info_json(self, build_stats: dict) -> tuple[dict, str]:
        try:
            run_info_json = build_stats["run_info"]
            run_id = run_info_json["id"]
        except KeyError:
            raise BadDataError("Missing run_info/id in payload")
        return run_info_json, run_id

    def ingest_work_units(
        self, user_api_id: str, run_id: str, accept_time: datetime.datetime, workunits_json: list[dict]
    ) -> bool:
        # TODO: store to s3, just in case?
        # Probably need a different logic to parse this data coming from the API endpoint. but this will do for now.
        running_wus = [wu for wu in workunits_json if wu.get("state") != "finished"]
        running_wu_str = ", ".join(wu["name"] for wu in running_wus[:30])
        _logger.debug(  # this can be super noisy in prod
            f"ingest_work_units repo={self._repo.slug} run_id={run_id} total={len(workunits_json)} running={len(running_wus)} {running_wu_str}"
        )
        # Disable parsing WU while we transition their format
        # workunits = WorkUnit.from_json_dicts(workunits_json)
        return self._table.update_workunits(
            repo_id=self._repo.pk, user_api_id=user_api_id, run_id=run_id, last_update=accept_time, workunits=[]
        )

    def queue_batched_builds(
        self,
        batched_builds: dict[str, dict] | IO[bytes],
        user_api_id: str,
        accepted_time: datetime.datetime,
        request_id: str,
        num_of_builds: int,
    ) -> None:
        queue = BatchedBuildsQueue.for_repo(self._repo)
        bucket, key = queue.queue_builds(
            batched_builds=batched_builds, user_api_id=user_api_id, accepted_time=accepted_time, request_id=request_id
        )
        ProcessQueuedBuilds.create(repo=self._repo, bucket=bucket, key=key, num_of_builds=num_of_builds)

    def save_run_log(self, run_id: str, user_api_id: str, fp: IO[bytes]) -> None:
        self._raw_store.save_artifact(
            run_id=run_id,
            user_api_id=user_api_id,
            content_type=RUN_LOGS_ARTIFACTS_CONTENT_TYPE,
            name=RUN_LOGS_ARTIFACTS_FILE_NAME,
            fp=fp,
            is_compressed=True,
            metadata=None,
        )

    def ingest_artifact(self, run_id: str, user_api_id: str, descriptor: dict[str, str], fp: IO[bytes]) -> bool:
        def normalize(data: str) -> str:
            return data.replace("/", "_")

        run_info = self._table.get_by_run_id(repo_id=self._repo_id, user_api_id=user_api_id, run_id=run_id)
        if not run_info:
            return False
        # TODO: check outcome? check build time (make sure it is not too old)
        name = descriptor["name"]
        path = descriptor["path"]
        content_type = self._ARTIFACT_CONTENT_TYPE.get(name, "unknown")
        metadata = {
            "workunit_id": descriptor["workunit_id"],
            "name": name,
            "path": path,
        }
        key_name = f"{normalize(name)}_{normalize(path)}"
        self._raw_store.save_artifact(
            run_id=run_id,
            user_api_id=user_api_id,
            content_type=content_type,
            name=key_name,
            fp=fp,
            metadata=metadata,
            is_compressed=True,
        )
        return True
