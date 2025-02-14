#!/usr/bin/env ./python
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
from argparse import ArgumentParser, Namespace

from toolchain.aws.eks import EKS, ClusterOIDCInfo
from toolchain.aws.iam import IAM
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.config.services import get_region_for_cluster
from toolchain.prod.tools.utils import get_k8s_service_role_name

logger = logging.getLogger(__name__)


class EnsureK8SServiceRole(ToolchainBinary):
    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._cluster = cmd_args.cluster
        self._aws_region = get_region_for_cluster(self._cluster)
        self._service = cmd_args.service
        self._dry_run = cmd_args.dry_run

    def run(self) -> int:
        iam = IAM(region=self._aws_region)
        eks = EKS(region=self._aws_region)
        oidc_info = eks.get_cluster_oidc_info(cluster_name=self._cluster)
        role_name = get_k8s_service_role_name(self._cluster, self._service)
        assume_role_policy = self._get_assume_role_policy(oidc_info=oidc_info)
        if self._dry_run:
            logger.info(f"Role [dry_run] {role_name=}")
            return 0
        created = iam.ensure_role(role_name=role_name, assume_role_policy=assume_role_policy)
        logger.info(f"Role {role_name} { 'created' if created else 'updated'}")
        return 0

    def _get_assume_role_policy(self, oidc_info: ClusterOIDCInfo) -> dict:
        service_account_name = self._service.replace("/", "-")  # see: prod/helm/base/workflow/templates/_worker.yaml
        return {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": "sts:AssumeRoleWithWebIdentity",
                    "Principal": {"Federated": oidc_info.provider_arn},
                    "Condition": {
                        "StringLike": {
                            # Allow all namespaces for this role, for dev cluster we have a ns for every eng, and in prod clusters we want this to cover both prod and staging.
                            # We can consider locking this down for prod and only allow certain namespaces here.
                            f"{oidc_info.provider_uri}:sub": f"system:serviceaccount:*:{service_account_name}"
                        }
                    },
                },
            ],
        }

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        parser.add_argument("--cluster", metavar="name", required=True, help="The Kubernetes cluster for the role.")
        parser.add_argument("--service", metavar="name", required=True, help="The service for the role.")
        parser.add_argument("--dry-run", action="store_true", required=False, default=False, help="Dry run.")


if __name__ == "__main__":
    EnsureK8SServiceRole.start()
