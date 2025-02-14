# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

from toolchain.aws.s3 import S3
from toolchain.buildsense.build_data_queries import BuildsQueries
from toolchain.buildsense.ingestion.models import ProcessPantsRun
from toolchain.buildsense.ingestion.pants_data_ingestion import PantsDataIngestion
from toolchain.django.site.models import Repo

_logger = logging.getLogger(__name__)


class BuildsMover:
    @classmethod
    def for_local_dev(cls, env_name: str, dry_run=True):
        return cls(
            aws_region="us-east-1",
            bucket_name="staging.buildstats-dev.us-east-1.toolchain.com",
            bucket_path=f"{env_name}/buildstatsv1",
            env_name=env_name,
            dry_run=dry_run,
        )

    @classmethod
    def for_django_command(cls, django_settings, dry_run):
        return cls(
            aws_region=django_settings.AWS_REGION,
            bucket_name=django_settings.BUILDSENSE_BUCKET,
            bucket_path=django_settings.BUILDSENSE_STORAGE_BASE_S3_PATH,
            env_name=django_settings.TOOLCHAIN_ENV.get_env_name(),
            dry_run=dry_run,
        )

    def __init__(self, *, aws_region, bucket_name, bucket_path, env_name, dry_run):
        self._s3 = S3(aws_region)
        self._bucket_name = bucket_name
        self._env_name = env_name
        self._bucket_path = bucket_path
        self._dry_run = dry_run

    def _process_key(self, s3_key_dict, target_repo) -> bool:
        dry_run_str = "[Dry]" if self._dry_run else ""
        s3_key = s3_key_dict["Key"]
        key_parts = s3_key.replace(self._bucket_path + "/", "").split("/")
        if "duplicates" in key_parts:
            return False
        user_api_id = key_parts[2]
        repo = Repo.get_or_none(id=key_parts[1])
        run_id = key_parts[3]

        queries = BuildsQueries.for_customer_id(repo.customer_id)
        pdi = PantsDataIngestion.for_reprocess_scripts(env_name=self._env_name, repo=target_repo)
        run_info = queries.get_build(repo_id=repo.pk, user_api_id=user_api_id, run_id=run_id)
        if not run_info:
            _logger.info(f"{dry_run_str} skip {run_id}")
            return False

        build_stats = queries.get_build_raw_data(repo=repo, user_api_id=user_api_id, run_id=run_id)
        s3_bucket_name, new_s3_key = pdi._raw_store.save_final_build_stats(
            run_id=run_id, build_stats=build_stats, user_api_id=user_api_id, ignore_dups=True, dry_run=self._dry_run
        )
        run_info.server_info.s3_bucket = s3_bucket_name
        run_info.server_info.s3_key = new_s3_key

        run_info.repo_id = target_repo.id
        run_info.customer_id = target_repo.customer_id
        written = self._dry_run or pdi._table.save_run(run_info)

        if not written:
            _logger.warning(f"Did not save {run_id} from {s3_key} --- to {new_s3_key}")
            return False
        _logger.info(f"{dry_run_str} Moved {run_id} from {s3_key} --- to {new_s3_key}")
        if not self._dry_run:
            ProcessPantsRun.create(run_info, repo=repo)
        return True

    def move_builds(self, *, src_repo_slug: str, tgt_repo_slug: str) -> tuple[int, int]:
        _logger.info(
            f"runs: {ProcessPantsRun.objects.count()}"
        )  # Checks that django is setup and we can access the DB.
        src_repo = Repo.objects.get(slug=src_repo_slug)
        tgt_repo = Repo.objects.get(slug=tgt_repo_slug)
        src_prefix = f"{self._bucket_path}/{src_repo.customer_id}/{src_repo.id}"
        total_count = 0
        migrated_count = 0
        for s3_key_dict in self._s3.key_metadata_with_prefix(bucket=self._bucket_name, key_prefix=src_prefix):
            total_count += 1
            migrated = self._process_key(s3_key_dict=s3_key_dict, target_repo=tgt_repo)
            if migrated:
                migrated_count += 1
        return total_count, migrated_count
