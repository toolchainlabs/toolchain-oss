# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

import pkg_resources
from ruamel.yaml import YAML

from toolchain.kubernetes.application_api import KubernetesApplicationAPI
from toolchain.kubernetes.batch_api import JobStatus, KubernetesBatchAPI
from toolchain.kubernetes.constants import KubernetesCluster
from toolchain.prod.tools.utils import get_k8s_service_role_name

_logger = logging.getLogger(__name__)


def load_resource(name: str) -> str:
    resource = pkg_resources.resource_string(__name__, f"resources/{name}")
    return resource.decode()


class JobHelper:
    Status = JobStatus
    _MAX_REPO_NAME_LENGTH = 35  # label values can be up to 63 charecters, but for the job name (for example) we need to leave space for our prefix

    def __init__(
        self,
        *,
        container_image: str,
        instance_category: str,
        cluster: KubernetesCluster,
        namespace: str,
        service_name: str,
        is_running_in_k8s: bool,
        push_gateway_url: str | None = None,
    ) -> None:
        self._container_image = container_image
        self._instance_category = instance_category
        self._cluster = cluster
        self._push_gateway_url = push_gateway_url
        self._k8s_batch = (
            KubernetesBatchAPI.for_pod(namespace=namespace)
            if is_running_in_k8s
            else KubernetesBatchAPI.for_cluster(namespace=namespace, cluster=cluster)
        )
        self._k8s_apps = (
            KubernetesApplicationAPI.for_pod(namespace=namespace)
            if is_running_in_k8s
            else KubernetesApplicationAPI.for_cluster(namespace=namespace, cluster=cluster)
        )
        self._iam_role = get_k8s_service_role_name(cluster=cluster.value, service=service_name)

    def _normalize_repo(self, repo: str) -> str:
        normalized = repo.replace("/", "-").replace("_", "-").lower()
        if len(normalized) > self._MAX_REPO_NAME_LENGTH:
            normalized = normalized.replace("-", "")
        return normalized[: self._MAX_REPO_NAME_LENGTH - 2]

    def _load_template_and_set_name(self, repo: str) -> tuple[dict, str]:
        job_def = YAML().load(load_resource("job_template.yaml"))
        job_base_name = job_def["metadata"]["name"]
        normalized_repo_name = self._normalize_repo(repo)
        job_name = f"{job_base_name}-{normalized_repo_name}"
        job_def["metadata"]["name"] = job_name
        return job_def, job_name

    def configure_job_template(self, repo: str, s3_url: str, s3_url_fields: str) -> tuple[dict, str]:
        job_def, job_name = self._load_template_and_set_name(repo)
        pod_template = job_def["spec"]["template"]
        pod_template["metadata"]["labels"]["repo"] = self._normalize_repo(repo)
        pod_template["spec"]["nodeSelector"]["toolchain.instance_category"] = self._instance_category
        container = pod_template["spec"]["containers"][0]
        container["args"].extend(("--repo", repo, "--s3-url", s3_url, "--s3-url-fields", s3_url_fields))
        if self._push_gateway_url:
            container["args"].extend(("--push-gateway-url", self._push_gateway_url))
        container["image"] = self._container_image
        return job_def, job_name

    def create_job(self, repo: str, s3_url: str, s3_url_fields: str) -> str:
        job_def, job_name = self.configure_job_template(repo=repo, s3_url=s3_url, s3_url_fields=s3_url_fields)
        _logger.info(f"Create pants demo job {job_name=} for {repo=}")
        self._k8s_batch.create_job_from_data(job_data=job_def)
        return job_name

    def get_job_status(self, repo: str) -> JobStatus:
        _, job_name = self._load_template_and_set_name(repo)
        job_status = self._k8s_batch.get_job_status(job_name)
        if job_status in (JobStatus.FAILED, JobStatus.SUCCEEDED):
            # TODO: maybe capture logs if the job failed? will look into it later.
            pod_info = self._k8s_apps.get_pod_info_with_labels(**{"job-name": job_name})
            self._k8s_batch.delete_job(job_name)
            if pod_info:
                self._k8s_apps.delete_pod_by_name(pod_info.name)
            else:
                _logger.warning(f"can't find pod for job: {job_name}")
        return job_status

    def get_current_jobs_count(self) -> int:
        # See job_template.yaml
        pods = self._k8s_apps.get_pods_infos_with_labels(toolchain_role="run-pants")
        return sum(pod.is_running for pod in pods)
