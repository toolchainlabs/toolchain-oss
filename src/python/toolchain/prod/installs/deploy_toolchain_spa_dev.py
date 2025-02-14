#!/usr/bin/env ./python
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from argparse import ArgumentParser, Namespace

from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.constants import ToolchainEnv
from toolchain.kubernetes.constants import KubernetesCluster
from toolchain.prod.installs.deploy_frontend import BuildAndDeployToolchainSPA
from toolchain.prod.tools.deploy_notifications import Deployer
from toolchain.prod.tools.utils import check_cluster_connectivity


class BuildAndDeployToolchainSPADev(ToolchainBinary):
    BUCKET = "assets-dev.us-east-1.toolchain.com"

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._namespace = cmd_args.namespace or "shared"
        self._action = cmd_args.action
        self._deploy = BuildAndDeployToolchainSPA.create(
            aws_region=cmd_args.aws_region,
            bucket=self.BUCKET,
            base_key=f"dev/frontend/{self._namespace}",
            tc_env=ToolchainEnv.DEV,  # type: ignore[attr-defined]
            deployer=Deployer.get_current(),
            cluster=KubernetesCluster.DEV,
        )
        check_cluster_connectivity(KubernetesCluster.DEV)

    def run(self) -> int:
        success = self._run_action(self._action)
        return 0 if success else -1

    def _run_action(self, action: str) -> bool:
        ns = self._namespace
        skip_reload = ns == "shared"
        if action == "rollback":
            return self._deploy.rollback(namespace=ns, skip_reload=skip_reload)
        if action == "deploy":
            return self._deploy.deploy(namespace=ns, skip_reload=skip_reload, allow_invalid_commits=True)
        if action == "purge":
            return self._deploy.purge_old_versions(namespace=ns, dry_run=False)
        raise ToolchainAssertion(f"Invalid action: {self._action}")

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        cls.add_aws_region_argument(parser)
        parser.add_argument(
            "--namespace", type=str, action="store", default=None, help="namespace to associate with bundles."
        )
        parser.add_argument("action", choices=("deploy", "rollback", "purge"), help="Action to perform")


if __name__ == "__main__":
    BuildAndDeployToolchainSPADev.start()
