# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
import logging
import re
import uuid
import zlib

from django.conf import settings
from django.core.management.base import BaseCommand

from toolchain.aws.s3 import S3
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.buildsense.build_data_queries import BuildsQueries
from toolchain.buildsense.ingestion.integrations.ci_scm_helpers import ScmInfoHelper
from toolchain.buildsense.ingestion.models import ProcessPantsRun
from toolchain.buildsense.ingestion.pants_data_ingestion import PantsDataIngestion
from toolchain.buildsense.records.adapters import from_post_data
from toolchain.buildsense.records.run_info import RunInfo, ServerInfo
from toolchain.django.site.models import Repo, ToolchainUser

_logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Reimport builds from s3"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", required=False, default=False, help="Dry run.")
        parser.add_argument(
            "--path",
            type=str,
            required=False,
            default=None,
            help="s3 key path (after BUILDSENSE_STORAGE_BASE_S3_PATH) to process.",
        )

    def handle(self, *args, **options):
        root = settings.BUILDSENSE_STORAGE_BASE_S3_PATH
        importer = BuildsImporter(
            region=settings.AWS_REGION,
            bucket=settings.BUILDSENSE_BUCKET,
            env_name=settings.TOOLCHAIN_ENV.get_env_name(),
            root=root,
            dry_run=options["dry_run"],
        )
        key_prefix = options["path"] or ""
        self.stdout.write(self.style.NOTICE(f"Processing keys from: {root}/{key_prefix}"))
        importer.import_from_env(key_prefix)


class BuildsImporter:
    """Scan build data in s3 and import into dynamodb.

    Use Cases:
     * We added fields to RunInfo and need to create those based on data in s3 (For example,
       this was used when ServerInfo was added).
     * Failure to insert data to dynamodb.
     * Re-queue async processing logic - as we add more stuff we calculate async this can be used to
       queue this work and backfill data on existing items in DynamoDB.
     * Import builds copied directly to s3 from one environment to another environment (for example to populate dev data from prod)
    """

    _KEY_STRUCTURE = re.compile(
        r".*/(?P<customer_id>[A-Za-z0-9]+)/(?P<repo_id>[A-Za-z0-9]+)/(?P<user_api_id>[A-Za-z0-9]+)/(?P<run_id>[A-Za-z0-9_]+)/final\.json$"
    )

    def __init__(self, region: str, bucket: str, env_name: str, root: str, dry_run: bool) -> None:
        self._s3 = S3(region)
        self._bucket_name = bucket
        self._env_name = env_name
        self._dry_run = dry_run
        self._root = root

    def _generate_request_id(self) -> str:
        fields = list(uuid.uuid4().fields)
        fields[0] = 0xFFFFFFFF
        return str(uuid.UUID(fields=tuple(fields)))  # type: ignore

    def _get_server_info(self, s3_key: str, last_modified: datetime.datetime) -> ServerInfo:
        return ServerInfo(
            s3_bucket=self._bucket_name,
            s3_key=s3_key,
            stats_version="3",
            environment=self._env_name,
            accept_time=last_modified,
            request_id=self._generate_request_id(),
        )

    def _load_build_stats(self, s3_key: str) -> dict:
        build_stats_bytes, info = self._s3.get_content_with_object(bucket=self._bucket_name, key=s3_key)
        compression = info.metadata.get("compression")
        if compression == "zlib":
            return json.loads(zlib.decompress(build_stats_bytes))
        if compression is None:
            return json.loads(build_stats_bytes)
        raise ToolchainAssertion(f"Unexpected compression value {compression=} for {s3_key=}")

    def _process_key(self, s3_key_dict: dict) -> RunInfo | None:
        s3_key = s3_key_dict["Key"]
        _logger.info(f"process {s3_key}")
        if "duplicates" in s3_key:
            return None
        match = self._KEY_STRUCTURE.match(s3_key)
        if not match:
            _logger.warning(f"Can't match key structure {s3_key=}")
            return None
        groups = match.groupdict()
        run_id = groups["run_id"]
        repo = Repo.objects.get(pk=groups["repo_id"])
        user = ToolchainUser.objects.get(api_id=groups["user_api_id"])
        if repo.customer_id != groups["customer_id"]:
            raise ToolchainAssertion(f"customer id mismatch {groups=} {repo.customer_id=}")

        pdi = PantsDataIngestion.for_reprocess_scripts(env_name=self._env_name, repo=repo)
        scm = ScmInfoHelper(customer_id=repo.customer_id, repo_id=repo.pk, silence_timeouts=False)
        run_info = BuildsQueries.for_customer_id(repo.customer_id).get_build(
            repo_id=repo.id, user_api_id=user.api_id, run_id=run_id
        )
        if not run_info:
            return self._add_to_dynamodb(s3_key_dict, run_id, pdi, user)
        if run_info.server_info.s3_key != s3_key:
            _logger.info(f"Update s3 key: {run_id} old: {run_info.server_info.s3_key} new {s3_key}")
            run_info.server_info.s3_key = s3_key
            run_info.server_info.s3_bucket = self._bucket_name
        if run_info.ci_info is None:
            build_data = self._load_build_stats(s3_key)
            ci_full_details, _ = scm.get_ci_info(run_id, build_data, user, user)
            if ci_full_details:
                run_info.ci_info = ci_full_details.details
        else:
            _logger.info(
                f"no updates to do with {run_id} accepted at {run_info.server_info.accept_time} queue async processing"
            )
        if not self._dry_run:
            written = pdi._table.save_run(run_info)
            ProcessPantsRun.create(run_info, repo=repo)
        else:
            written = True
        if not written:
            raise ToolchainAssertion(f"Should have updated for {run_info.run_id} from {s3_key}")
        return run_info

    def _add_to_dynamodb(self, s3_key_dict: dict, run_id: str, pdi: PantsDataIngestion, user) -> RunInfo | None:
        last_modified = s3_key_dict["LastModified"]
        s3_key = s3_key_dict["Key"]
        server_info = self._get_server_info(s3_key, last_modified)
        build_data = self._load_build_stats(s3_key)

        if run_id != build_data["run_info"]["id"]:
            raise ToolchainAssertion(f"Unexpected run_id ({run_id}) for: {s3_key}")
        _logger.info(f"New RunInfo for {run_id} from {s3_key}")
        if self._dry_run:
            return None
        run_info_json, run_id = pdi._get_run_info_json(build_data)
        repo = pdi._repo
        scm = ScmInfoHelper(customer_id=repo.customer_id, repo_id=repo.pk, silence_timeouts=False)
        ci_full_details, _ = scm.get_ci_info(run_id=run_id, build_stats=build_data, auth_user=user, ci_user=user)
        del build_data["run_info"]["id"]
        run_info = from_post_data(
            run_id=run_id,
            run_info_json=run_info_json,
            repo=repo,
            user=user,
            server_info=server_info,
            ci_details=ci_full_details.details if ci_full_details else None,
        )
        pdi._table.save_run(run_info)
        ProcessPantsRun.create(run_info, repo=repo)
        return run_info

    def import_from_env(self, path: str):
        key_prefix = f"{self._root}/{path}"
        for s3_key_dict in self._s3.key_metadata_with_prefix(bucket=self._bucket_name, key_prefix=key_prefix):
            self._process_key(s3_key_dict=s3_key_dict)
