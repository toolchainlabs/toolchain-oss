# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import logging
from enum import Enum, unique

from kubernetes.client import ApiClient, ApiException, BatchV1Api, V1Job

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.kubernetes.kubernetes_api import KubernetesAPI

_logger = logging.getLogger(__name__)


@unique
class JobStatus(Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    NOT_AVAILABLE = "na"


class FakeResponse:
    def __init__(self, response_data: dict) -> None:
        self.data = json.dumps(response_data)


class KubernetesBatchAPI(KubernetesAPI):
    def __init__(self, namespace) -> None:
        super().__init__(namespace)
        self._batch_api = BatchV1Api()

    def create_job_from_data(self, job_data: dict) -> str:
        # The kubernetes client doesn't expose an easy way to take a dict/json data and create a model instance out of it.
        # so we fool the api client by passing it a fake response object and having it deserialize the json data into a model object.
        job_def = ApiClient().deserialize(FakeResponse(job_data), V1Job)
        self._batch_api.create_namespaced_job(self.namespace, job_def)
        return job_def.metadata.name

    def delete_job(self, job_name: str) -> None:
        _logger.info(f"delete job {job_name=} namespace={self._namespace}")
        self._batch_api.delete_namespaced_job(name=job_name, namespace=self.namespace)

    def get_job_status(self, job_name: str) -> JobStatus:
        try:
            job = self._batch_api.read_namespaced_job_status(name=job_name, namespace=self.namespace)
        except ApiException as error:
            if error.status == 404:  # legit state when job no longer exists
                return JobStatus.NOT_AVAILABLE
            _logger.warning(f"read_namespaced_job_status for {job_name} failed: {error}")
            raise
        job_status_str = " ".join(f"{k}={v}" for k, v in job.status.to_dict().items())
        _logger.debug(f"Job: {job_name} status: {job_status_str}")
        if job.status.active:
            return JobStatus.RUNNING
        if job.status.succeeded:
            return JobStatus.SUCCEEDED
        if job.status.failed:
            return JobStatus.FAILED
        raise ToolchainAssertion(f"Unexpected job status: {job_name=} status={job_status_str}")
