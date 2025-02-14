# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json
import socket
from argparse import ArgumentParser, Namespace
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, unique

from toolchain.aws.ec2 import EC2
from toolchain.aws.elasticsearch import ElasticSearch
from toolchain.aws.secretsmanager import SecretsManager
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.config.services import ToolchainService
from toolchain.constants import ToolchainEnv
from toolchain.kubernetes.cluster import ClusterAPI
from toolchain.kubernetes.constants import KubernetesCluster, KubernetesProdNamespaces
from toolchain.util.net.net_util import get_remote_username
from toolchain.util.prod.exceptions import NotConnectedToClusterError


@unique
class IngressType(Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    PEER = "peer"


_INGRESS_SG_MAP = {
    IngressType.PUBLIC: "k8s.{cluster_name}.ingress",
    IngressType.PRIVATE: "k8s.{cluster_name}.vpn.ingress",
    IngressType.PEER: "k8s.{cluster_name}.vpc-ingress",
}

PROD_MONITORING_SECRET_NAME = "prod/monitoring"


def get_ingress_security_group_id(aws_region: str, cluster: KubernetesCluster, ingress_type: IngressType) -> str:
    group_name = _INGRESS_SG_MAP[ingress_type].format(cluster_name=cluster.value)
    sg_id = EC2(aws_region).get_security_group_id_by_name(group_name)
    if not sg_id:
        raise ToolchainAssertion(f"Security group '{group_name}' not found.")
    return sg_id


def get_cluster(services: Sequence[ToolchainService]) -> KubernetesCluster:
    clusters = {svc.cluster for svc in services}
    if len(clusters) > 1:
        raise ToolchainAssertion("Installing services into multiple clusters is not supported.")
    return clusters.pop()


def get_logging_opensearch_endpoint(aws_region: str) -> str:
    es = ElasticSearch(aws_region)
    return es.get_domain_endpoint(tags={"app": "logging", "env": ToolchainEnv.PROD.value})  # type: ignore[attr-defined]


@dataclass(frozen=True)
class Deployer:
    user: str
    machine: str

    @classmethod
    def get_current(cls):
        return cls(user=get_remote_username(), machine=socket.gethostname())

    @property
    def formatted_deployer(self) -> str:
        return f"{self.user} @ {self.machine}"


def set_config_values(config: str, **kwargs) -> str:
    lines = []
    for line in config.splitlines():
        stripped_line = line.strip()
        if stripped_line.startswith("["):
            lines.append(line)
        else:
            new_line = line
            for key, value in kwargs.items():
                if stripped_line.startswith(key):
                    # ident must be 4 spaces.
                    new_line = f"    {key}  {value}"
                    break
            lines.append(new_line)
    return "\n".join(lines)


def get_monitoring_secret(aws_region: str) -> dict:
    secrets_mgr = SecretsManager(region=aws_region)
    secret = secrets_mgr.get_secret(PROD_MONITORING_SECRET_NAME)
    if not secret:
        raise ToolchainAssertion("Can't load monitoring secret from AWS")
    return json.loads(secret)


def get_slack_webhook_url(aws_region: str) -> str:
    # TODO: Stop using the monitoring secret/slack webhook for devops stuff
    return get_monitoring_secret(aws_region)["slack-webhook"]


def check_cluster_connectivity(cluster: KubernetesCluster) -> None:
    if not ClusterAPI.is_connected_to_cluster(cluster):
        raise NotConnectedToClusterError(cluster)


def add_profile_and_customer_args(parser: ArgumentParser) -> None:
    parser.add_argument("--customer", type=str, action="store", required=True, help="Customer slug.")
    parser.add_argument(
        "--aws-profile",
        type=str,
        action="store",
        required=False,
        help="AWS profile name. If not specified it defaults to a profile based on the customer name, for example: toolchainlans-remote-exec for customer toolchainlabs.",
    )


def get_namespace_for_cmd_args(cmdline_args: Namespace) -> str:
    # TODO: more namespaces based logic to be added here
    if "edge" in cmdline_args and cmdline_args.edge:
        return KubernetesProdNamespaces.EDGE
    if "staging" in cmdline_args:
        return KubernetesProdNamespaces.STAGING if cmdline_args.staging else KubernetesProdNamespaces.PROD
    if "prod" in cmdline_args:
        return KubernetesProdNamespaces.PROD if cmdline_args.prod else KubernetesProdNamespaces.STAGING
    raise ToolchainAssertion(
        f"Unexpected command line args configured for tool, can't determine namespace. configured args: {', '.join(cmdline_args.__dict__.keys())}"
    )


def set_fluentbit_service_account_annotation(cfg_values: dict, aws_region: str, cluster: KubernetesCluster) -> None:
    set_service_account_annotations(cfg_values, aws_region=aws_region, cluster=cluster, service="fluent-bit.service")


def get_curator_iam_role_arn_for_cluster(aws_region: str, cluster: KubernetesCluster) -> str:
    return get_aws_role_arn(aws_region, iam_role_name_for_cluster(cluster, "es-logging-curator.job"))


def get_k8s_service_role_name(cluster: str, service: str) -> str:
    return f'k8s.{cluster}.{service.replace("/", "-")}.service'


def get_k8s_service_role_arn(aws_region: str, cluster: str, service: str) -> str:
    role_name = get_k8s_service_role_name(cluster, service)
    return get_aws_role_arn(aws_region, role_name)


def get_aws_role_arn(aws_region: str, role_name: str) -> str:
    aws_account_id = EC2(region=aws_region).account_id
    return f"arn:aws:iam::{aws_account_id}:role/{role_name}"


def set_service_iam_role_values(cfg_values: dict, region: str, cluster: KubernetesCluster, service: str) -> None:
    service_role_arn = get_k8s_service_role_arn(aws_region=region, cluster=cluster.value, service=service)
    if "iam_service_role_arn" in cfg_values:
        cfg_values["iam_service_role_arn"] = service_role_arn


def iam_role_name_for_cluster(cluster: KubernetesCluster, service: str) -> str:
    return f"k8s.{cluster.value}.{service}"


def set_service_account_annotations(
    cfg_values: dict, aws_region: str, cluster: KubernetesCluster, service: str
) -> None:
    role_name = iam_role_name_for_cluster(cluster, service)
    role_arn = get_aws_role_arn(aws_region=aws_region, role_name=role_name)
    service_account_annotations = cfg_values["serviceAccount"]["annotations"]
    if "eks.amazonaws.com/role-arn" not in service_account_annotations:
        raise ToolchainAssertion(f"missing service account annotation: {service_account_annotations}")
    service_account_annotations["eks.amazonaws.com/role-arn"] = role_arn
