#!/usr/bin/env ./python
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from argparse import ArgumentParser, Namespace

from toolchain.aws.cloudfront import Cloudfront
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.constants import ToolchainEnv
from toolchain.kubernetes.constants import KubernetesCluster, KubernetesProdNamespaces
from toolchain.prod.installs.deploy_frontend import BuildAndDeployPantsDemoSite
from toolchain.prod.installs.deploy_toolchain_spa_prod import BuildAndDeployToolchainSPAProd
from toolchain.prod.tools.changes_helper import ChangeHelper
from toolchain.prod.tools.deploy_notifications import Deployer
from toolchain.prod.tools.deployment_lock import DeploymentLock
from toolchain.prod.tools.utils import check_cluster_connectivity


class BuildAndDeployPantsDemositeProd(ToolchainBinary):
    BUCKET = BuildAndDeployToolchainSPAProd.BUCKET
    CF_DIST_TAGS = {"toolchain_env": "production", "toolchain_app_name": "prod-pants-demo-site"}

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._action = cmd_args.action
        if self._action != "purge" and cmd_args.dry_run:
            raise ToolchainAssertion(f"Dry run can only be specified for purge command. (command: {self._action})")
        self._dry_run = cmd_args.dry_run
        self._cloudfront = Cloudfront(cmd_args.aws_region)
        self._deployer = Deployer.get_current()
        self._installer = BuildAndDeployPantsDemoSite.create(
            aws_region=cmd_args.aws_region,
            bucket=self.BUCKET,
            base_key="prod/pants-demo-site",
            tc_env=ToolchainEnv.PROD,  # type: ignore[attr-defined]
            deployer=self._deployer,
            cluster=KubernetesCluster.PROD,
        )
        check_cluster_connectivity(KubernetesCluster.PROD)

    def _get_lock(self) -> DeploymentLock:
        return DeploymentLock.for_deploy("pants_demo_site", self._deployer)

    def _deploy_staging(self) -> bool:
        if not ChangeHelper.check_git_state():
            return False
        domain = self._cloudfront.get_distribution_for_tags(self.CF_DIST_TAGS).domain
        with self._get_lock():
            return self._installer.deploy(
                namespace=KubernetesProdNamespaces.STAGING, domain=domain, allow_invalid_commits=False
            )

    def purge(self) -> bool:
        return self._installer.purge_old_versions(namespace=KubernetesProdNamespaces.PROD, dry_run=self._dry_run)

    def run(self) -> int:
        self._installer.check_cluster_connectivity()
        if self._action == "stage":
            success = self._deploy_staging()
        elif self._action == "promote":
            with self._get_lock():
                success = self._installer.promote(
                    source_namespace=KubernetesProdNamespaces.STAGING, target_namespace=KubernetesProdNamespaces.PROD
                )
        elif self._action == "purge":
            success = self.purge()
        elif self._action.startswith("rollback"):
            namespace = (
                KubernetesProdNamespaces.PROD if self._action == "rollback" else KubernetesProdNamespaces.STAGING
            )
            with self._get_lock():
                success = self._installer.rollback(namespace)
        else:
            raise ToolchainAssertion(f"Invalid action: {self._action}")
        return 0 if success else -1

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        parser.add_argument("--dry-run", action="store_true", required=False, default=False, help="Dry run [for purge]")
        parser.add_argument(
            "action",
            choices=(
                "stage",
                "promote",
                "rollback",
                "rollback-staging",
                "purge",
            ),
            help="Action to perform",
        )
        cls.add_aws_region_argument(parser)


if __name__ == "__main__":
    BuildAndDeployPantsDemositeProd.start()
