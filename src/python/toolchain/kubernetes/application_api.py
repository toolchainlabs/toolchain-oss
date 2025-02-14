# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from urllib.parse import urljoin

from kubernetes.client import V1Deployment, V1DeploymentSpec, V1LabelSelector, V1ObjectMeta, V1PodTemplateSpec

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.kubernetes.kubernetes_api import KubernetesAPI

_logger = logging.getLogger(__name__)

INTERNAL_POD_PORT = 8020  # see nginx config


@dataclass(frozen=True)
class PodInfo:
    name: str
    namespace: str
    phase: str
    start_time: datetime.datetime
    internal_endpoint: str
    annotation: str | None = None

    def get_url(self, path: str) -> str:
        return urljoin(self.internal_endpoint, path)

    @property
    def uptime(self) -> datetime.timedelta:
        return utcnow() - self.start_time

    @property
    def is_running(self) -> bool:
        return self.phase == "Running"

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"PodInfo(name={self.name} phase={self.phase})"

    @classmethod
    def from_pod(cls, pod, annotation_value=None):
        # This is super specific to how we run service right now. I might move it to a different place later on
        # For now, I want to avoid logic outside toolchain/kubernetes internacting directly w/ data structures defined in the
        # kubernetes python client.
        container_names = {container.name for container in pod.spec.containers}
        port = INTERNAL_POD_PORT if "nginx" in container_names else 8001
        ep = f"http://{pod.status.pod_ip}:{port}/"
        return cls(
            name=pod.metadata.name,
            namespace=pod.metadata.namespace,
            phase=pod.status.phase,
            start_time=pod.status.start_time,
            annotation=annotation_value,
            internal_endpoint=ep,
        )


PodsInfos = tuple[PodInfo, ...]


class KubernetesApplicationAPI(KubernetesAPI):
    """API class to interact with Kubernetes application related objects.

    This class provides methods to access application related entities in Kubernetes. Application related entities are:
    pods, services, deployments, etc...
    """

    def _paginate_pods(self, label_selector: str):
        cursor = None
        while True:
            # Specifying _continue=None causes an error.
            kwargs = {"_continue": cursor} if cursor else {}  # type: ignore
            response = self.api.list_namespaced_pod(self.namespace, label_selector=label_selector, **kwargs)
            yield from response.items
            cursor = response.metadata._continue
            if not cursor:
                return

    def paginate_pods_with_labels(self, **labels):
        labels_str = ",".join(f"{key}={value}" for key, value in labels.items())
        return self._paginate_pods(label_selector=labels_str)

    def get_pod_names_for_app(self, app_names: list[str]) -> Iterator[str]:
        """Get the names of pods that belong to any of the apps."""
        app_names_str = ", ".join(app_names)
        for pod in self._paginate_pods(label_selector=f"app in ({app_names_str})"):
            yield pod.metadata.name

    def get_pod_info_with_labels(self, **labels: dict[str, str]) -> PodInfo | None:
        pods = self.get_pods_infos_with_labels(**labels)
        if len(pods) > 1:
            raise ToolchainAssertion(f"Found {len(pods)} with labels  {labels}")
        return pods[0] if pods else None

    def get_pods_infos_with_labels(self, **labels: dict[str, str]) -> tuple[PodInfo, ...]:
        pods_iter = self.paginate_pods_with_labels(**labels)
        return tuple(PodInfo.from_pod(pod) for pod in pods_iter)

    def delete_pod_by_name(self, pod_name: str) -> None:
        _logger.info(f"Delete pod={pod_name} namespace={self._namespace}")
        self.api.delete_namespaced_pod(namespace=self._namespace, name=pod_name)

    def rollout_restart_deployment(self, deployment_name: str) -> None:
        _logger.info(f"Rollout restart deployment={deployment_name} namespace={self._namespace}")
        # see: https://stackoverflow.com/a/59051313/38265
        # https://github.com/kubernetes-client/python/issues/1378#issuecomment-838884280
        deployment = V1Deployment(
            spec=V1DeploymentSpec(
                selector=V1LabelSelector(),
                template=V1PodTemplateSpec(
                    metadata=V1ObjectMeta(annotations={"kubectl.kubernetes.io/restartedAt": utcnow().isoformat()})
                ),
            )
        )
        self.app_api.patch_namespaced_deployment(name=deployment_name, namespace=self._namespace, body=deployment)

    def get_pod_by_name(self, pod_name: str) -> PodInfo | None:
        pods = self.api.list_namespaced_pod(namespace=self._namespace, field_selector=f"metadata.name={pod_name}").items
        if not pods:
            return None
        if len(pods) > 1:
            raise ToolchainAssertion(f"More than one pod found with name: {pod_name}: {len(pods)} pods")
        return PodInfo.from_pod(pods[0])

    def get_pods_with_annotation(self, annotation_key, **labels) -> PodsInfos:
        pods: list[PodInfo] = []
        for pod in self.paginate_pods_with_labels(**labels):
            annotation_value = pod.metadata.annotations.get(annotation_key)
            if annotation_value:
                pods.append(PodInfo.from_pod(pod, annotation_value))
        return tuple(pods)

    def get_pending_replicas_count(self) -> tuple[int, str]:
        all_replica_sets = self.app_api.list_replica_set_for_all_namespaces().items
        running_sets = [rs for rs in all_replica_sets if rs.spec.replicas > 0]
        # rs.status.ready_replicas can be None
        pending = [rs for rs in running_sets if rs.spec.replicas > (rs.status.ready_replicas or 0)]
        pending_rs_str = ", ".join(f"{rs.metadata.name}@{rs.metadata.namespace}" for rs in pending) if pending else ""
        return len(pending), pending_rs_str

    def call_internal_endpoint(self, pod_name: str, method: str, path: str) -> bytes:
        # https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/CoreV1Api.md#connect_post_namespaced_pod_proxy_with_path
        api_func = getattr(self.api, f"connect_{method.lower()}_namespaced_pod_proxy_with_path")
        response = api_func(
            name=f"{pod_name}:{INTERNAL_POD_PORT}",
            namespace=self._namespace,
            path=path,
            async_req=False,
            _preload_content=False,
        )
        return response.data
