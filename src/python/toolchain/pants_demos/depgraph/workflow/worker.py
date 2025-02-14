# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
import logging
from pathlib import PurePath

from django.conf import settings
from prometheus_client import Counter

from toolchain.aws.s3 import S3
from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.kubernetes.constants import KubernetesCluster
from toolchain.pants_demos.depgraph.models import DemoRepo, GenerateDepgraphForRepo
from toolchain.pants_demos.depgraph.workflow.config import DepgraphWorkerConfig
from toolchain.pants_demos.depgraph.workflow.job_helper import JobHelper
from toolchain.workflow.config import WorkflowWorkerConfig
from toolchain.workflow.work_dispatcher import WorkDispatcher
from toolchain.workflow.worker import Worker

_logger = logging.getLogger(__name__)

REPO_PROCESSES_ERRORS = Counter(
    name="toolchain_pants_demo_depgraph_repo_process_errors",
    documentation="Count processed repos that resulted in an error",
    labelnames=("error",),
)

REPO_PROCESSED = Counter(
    name="toolchain_pants_demo_depgraph_repo_processed",
    documentation="Count processed repos",
)


class RepoDepgraphGenerator(Worker):
    work_unit_payload_cls = GenerateDepgraphForRepo
    MAX_CONCURRENT_JOBS = 3
    S3_LINK_TTL = datetime.timedelta(hours=3)
    # In production we want to run all the pants jobs/container in a dedicated namespace and not in the prod/staging namespace.
    PROD_JOBS_NAMESPACE = "pants-demos"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._demo_repo: DemoRepo | None = None
        self._config: DepgraphWorkerConfig = settings.DEPGRAPH_WORKER_CONFIG
        k8s_env = settings.K8S_ENV
        namespace = self.PROD_JOBS_NAMESPACE if settings.TOOLCHAIN_ENV.is_prod else settings.NAMESPACE
        instance_category = "database" if settings.TOOLCHAIN_ENV.is_dev else "worker"
        self._job_helper = JobHelper(
            container_image=self._config.job_container_image,
            instance_category=instance_category,
            cluster=k8s_env.cluster if k8s_env.is_running_in_kubernetes else KubernetesCluster.DEV,
            namespace=namespace,
            service_name=settings.SERVICE_INFO.name,
            is_running_in_k8s=k8s_env.is_running_in_kubernetes,
            push_gateway_url=self._config.push_gateway_url,
        )
        self._reschedule_delay = datetime.timedelta(seconds=10)

    def do_work(self, work_unit_payload: GenerateDepgraphForRepo) -> bool:
        demo_repo = DemoRepo.objects.get(id=work_unit_payload.demo_repo_id)
        if demo_repo.processing_state == DemoRepo.State.NOT_PROCESSED:
            self._maybe_process_repo(demo_repo)
            return False
        if demo_repo.processing_state == DemoRepo.State.PROCESSING:
            return self._handle_running(demo_repo)
        return True

    def on_reschedule(self, work_unit_payload: GenerateDepgraphForRepo) -> datetime.datetime | None:
        return utcnow() + self._reschedule_delay

    def _handle_running(self, demo_repo: DemoRepo) -> bool:
        status = self._job_helper.get_job_status(demo_repo.repo_full_name)
        if status == JobHelper.Status.RUNNING:
            return False
        if status == JobHelper.Status.NOT_AVAILABLE:
            _logger.warning(f"job for repo {demo_repo} N/A starting it again.")
            self._maybe_process_repo(demo_repo)
            return False
        if status not in (JobHelper.Status.SUCCEEDED, JobHelper.Status.FAILED):
            raise ToolchainAssertion(f"Unexpected depgraph job status: {status} for {demo_repo.repo_full_name}")
        s3 = S3()
        bucket, key = s3.parse_s3_url(demo_repo.result_location)
        result = s3.get_content_or_none(bucket=bucket, key=key)
        if not result:
            # TODO: Maybe raise an exception here to fail the WU?
            _logger.warning(f"Can't load result from {demo_repo.result_location}")
            demo_repo.set_failure_result(reason=f"no data in s3: job={status.value}", processing_time=None)
            return True
        # See: depgraph/job/demo.py
        REPO_PROCESSED.inc()
        results = json.loads(result)
        timing = results.get("timing")
        processing_time = datetime.timedelta(seconds=timing["processing"]) if timing else None
        errors = results.get("errors") or {}
        if not errors and status == JobHelper.Status.SUCCEEDED:
            repo_data = results["repo"]
            num_of_targets = len(results.get("target_list", []))
            demo_repo.set_success_result(
                branch=repo_data["branch"],
                commit_sha=repo_data["commit_sha"],
                num_of_targets=num_of_targets,
                processing_time=processing_time,
            )
        else:
            REPO_PROCESSES_ERRORS.labels(error=errors.get("stage") or "unknown").inc()
            reason = errors.get("message") or f"Job failure: {status}"
            demo_repo.set_failure_result(reason=reason, processing_time=processing_time)
        return True

    def _maybe_process_repo(self, demo_repo: DemoRepo) -> None:
        running_jobs = self._job_helper.get_current_jobs_count()
        if running_jobs >= self.MAX_CONCURRENT_JOBS:
            _logger.warning(f"too many running jobs: {running_jobs}")
            self._reschedule_delay = datetime.timedelta(seconds=40)
            return
        key_path = PurePath(self._config.base_path) / f"{demo_repo.repo_account}-{demo_repo.repo_name}.json"
        key = key_path.as_posix()
        s3_url = S3.get_s3_url(bucket=self._config.bucket, key=key)
        signed_url_response = S3().client.generate_presigned_post(
            Bucket=self._config.bucket,
            Key=key,
            ExpiresIn=int(self.S3_LINK_TTL.total_seconds()),
        )
        _logger.info(f"processing demo repo: {demo_repo} result={s3_url}")
        url_fields = json.dumps(signed_url_response["fields"])
        self._job_helper.create_job(
            repo=demo_repo.repo_full_name, s3_url=signed_url_response["url"], s3_url_fields=url_fields
        )
        demo_repo.start_processing(s3_url)


class PantsDepgraphDemoWorkDispatcher(WorkDispatcher):
    worker_classes = (RepoDepgraphGenerator,)

    @classmethod
    def for_django(cls, config: WorkflowWorkerConfig) -> PantsDepgraphDemoWorkDispatcher:
        return cls.for_worker_classes(config=config, worker_classes=cls.worker_classes)
