#!/usr/bin/env ./python
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
from argparse import ArgumentParser, Namespace

from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.config.services import get_service_config
from toolchain.kubernetes.constants import KubernetesCluster
from toolchain.prod.ensure_ecr_repo import EnsureEcrRepo
from toolchain.prod.ensure_k8s_service_role import EnsureK8SServiceRole

logger = logging.getLogger(__name__)


class EnsureServiceSetup(ToolchainBinary):
    description = "Ensures all setup for all services on all clusters."

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._dry_run = cmd_args.dry_run

    def run(self) -> int:
        service_config = get_service_config()
        for region, region_data in service_config["regions"].items():
            clusters = region_data["clusters"]
            for service in service_config["services"]:
                enabled = service.get("enabled", True)
                if not enabled:
                    continue
                service_name = service["name"]
                EnsureEcrRepo.run_for_service(region, service_name, dry_run=self._dry_run)
                service_cluster_alias = service.get("cluster")
                has_aws_role = service.get("use_aws", True)
                if has_aws_role:
                    if service_cluster_alias:
                        self._run_ensure_svc_role(clusters[service_cluster_alias]["name"], service_name)
                        # Also ensure that dev has the role.
                        if service_cluster_alias != KubernetesCluster.DEV.value:
                            self._run_ensure_svc_role(KubernetesCluster.DEV.value, service_name)
                    else:
                        for cluster in clusters.values():
                            if cluster.get("explicit", False):
                                continue
                            self._run_ensure_svc_role(cluster["name"], service_name)
        return 0

    def _run_ensure_svc_role(self, cluster: str, service: str) -> None:
        ensure_role = EnsureK8SServiceRole.create_for_args(cluster=cluster, service=service, dry_run=self._dry_run)
        ensure_role.run()

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        parser.add_argument("--dry-run", action="store_true", required=False, default=False, help="Dry run.")


if __name__ == "__main__":
    EnsureServiceSetup.start()
