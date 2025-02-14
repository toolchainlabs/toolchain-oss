# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import kubernetes

from toolchain.kubernetes.constants import KubernetesCluster


class KubernetesAPI:
    ApiException = kubernetes.client.rest.ApiException

    @classmethod
    def for_cluster(cls, cluster: KubernetesCluster | None, namespace: str | None = None):
        """Used when accessing the Kubernetes API from logic running outside the cluster."""
        kubernetes.config.load_kube_config(context=cluster.value if cluster else None)
        return cls(namespace=namespace)

    @classmethod
    def for_pod(cls, namespace: str | None = None):
        """Used when accessing the Kubernetes API from pods/containers running in the cluster."""
        kubernetes.config.load_incluster_config()
        return cls(namespace=namespace)

    def __init__(self, namespace: str | None):
        self._kubernetes_api = kubernetes.client.CoreV1Api()
        self._app_api = kubernetes.client.AppsV1Api()
        self._namespace = namespace

    @property
    def api(self):
        return self._kubernetes_api

    @property
    def app_api(self):
        return self._app_api

    @property
    def namespace(self) -> str | None:
        return self._namespace
