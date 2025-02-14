# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from kubernetes.client import V1Namespace, V1Node, V1NodeSpec, V1ObjectMeta, V1Taint
from kubernetes.config import ConfigException

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.kubernetes.constants import KubernetesCluster
from toolchain.kubernetes.kubernetes_api import KubernetesAPI


class ClusterAPI(KubernetesAPI):
    @classmethod
    def is_connected_to_cluster(cls, cluster: KubernetesCluster) -> bool:
        if not cluster:
            raise ToolchainAssertion("Empty cluster context name")
        try:
            cls.for_cluster(cluster=cluster)
        except ConfigException:
            return False
        return True

    def evict_pods_from_node(self, node_name: str) -> None:
        # The taint looks weird... but this is how it works.
        node_data = V1Node(spec=V1NodeSpec(taints=[V1Taint(effect="NoExecute", key="key", value="value")]))
        self.api.patch_node(node_name, node_data)

    def list_namespaces_of_type(self, namespace_type: str) -> list[str]:
        if not namespace_type:
            raise ToolchainAssertion("Must specify namespace type.")
        label_selector = f"ns_type in ({namespace_type})"
        namespaces_response = self.api.list_namespace(label_selector=label_selector)
        return [ns.metadata.name for ns in namespaces_response.items]

    def list_namespaces(self) -> list[str]:
        namespaces_response = self.api.list_namespace()
        return [ns.metadata.name for ns in namespaces_response.items]

    def create_namespace(
        self, namespace: str, labels: dict[str, str] | None = None, annotations: dict[str, str] | None = None
    ) -> None:
        ns_obj = V1Namespace(metadata=V1ObjectMeta(name=namespace, labels=labels, annotations=annotations))
        self.api.create_namespace(ns_obj)

    def get_namespace_annotation(self, namespace: str, annotation: str) -> str | None:
        if not namespace:
            raise ToolchainAssertion("Must specify namespace.")
        if not annotation:
            raise ToolchainAssertion("Must specify annotation.")
        namespaces = self.api.list_namespace(field_selector=f"metadata.name={namespace}").items
        if len(namespaces) != 1:
            raise ToolchainAssertion(f"Namespace mismatch on {namespace} found: {len(namespaces)}")
        annotations = namespaces[0].metadata.annotations
        return annotations.get(annotation) if annotations else None

    def get_not_ready_node_count(self) -> int:
        def _is_node_ready(node):
            for condition in node.status.conditions:
                if condition.type == "Ready":
                    return condition.status.lower() == "true"
            return False

        nodes = self.api.list_node().items
        return sum(1 for node in nodes if not _is_node_ready(node))

    def set_namespace_labels(self, namespace: str, labels: dict[str, str]) -> dict[str, str]:
        ns_obj = V1Namespace(metadata=V1ObjectMeta(labels=labels))
        ns_obj_response = self.api.patch_namespace(name=namespace, body=ns_obj)
        return ns_obj_response.metadata.labels

    def set_namespace_annotations(self, namespace: str, annotations: dict[str, str]) -> dict[str, str]:
        ns_obj = V1Namespace(metadata=V1ObjectMeta(annotations=annotations))
        ns_obj_response = self.api.patch_namespace(name=namespace, body=ns_obj)
        return ns_obj_response.metadata.annotations
