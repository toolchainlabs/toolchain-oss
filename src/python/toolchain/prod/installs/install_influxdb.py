#!/usr/bin/env ./python
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import logging
import re
from argparse import ArgumentParser, Namespace
from pathlib import Path

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.site.settings.util import maybe_prompt_k8s_port_fwd
from toolchain.kubernetes.constants import KubernetesCluster, KubernetesProdNamespaces
from toolchain.kubernetes.secret_api import SecretAPI
from toolchain.prod.tools.deploy_notifications import ChartDeployResults, Deployer
from toolchain.util.influxdb.client import InfluxDBConnectionConfig
from toolchain.util.influxdb.db_setup import InfluxDBUser, add_access_user, add_org, add_readonly_user
from toolchain.util.net.net_util import get_remote_username
from toolchain.util.prod.helm_charts import HelmChart
from toolchain.util.prod.helm_client import HelmClient
from toolchain.util.secret.secrets_accessor import KubernetesSecretsAccessor

_logger = logging.getLogger(__name__)


class InstallAndBootstrapInfluxDB(ToolchainBinary):
    LOCAL_CHART_PATH = Path("prod/helm/tools/influxdb")
    _LEGACY_MASTER_CREDS_SECRET_NAME = "influxdb-master-creds"
    _MASTER_CREDS_SECRET_NAME = "influxdb-auth"

    _ALLOWED_ORG_NAMES = re.compile(r"[a-z-]{4,15}")  # lower case letters and dashes. min length 4 max length: 15

    @classmethod
    def get_external_ro_user_secret_name(cls, service: str) -> str:
        return f"influxdb-{service}-ro-creds"

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        _logger.info(f"InstallAndBootstrapInfluxDB arguments: {cmd_args}")
        self._deployer = Deployer.get_current()
        self._override_users = cmd_args.override_users
        self._orgs = cmd_args.orgs or []
        self._validate_orgs(self._orgs)
        if cmd_args.prod:
            if cmd_args.namespace:
                raise ToolchainAssertion("Specifying namespace when targeting prod cluster is not supported.")
            cluster = KubernetesCluster.PROD
            self._namespaces = [KubernetesProdNamespaces.PROD]
            self._release_name = "influxdb-prod"
            self._instance_category = "worker"
        else:
            cluster = KubernetesCluster.DEV
            self._namespaces = [cmd_args.namespace or get_remote_username()]
            self._release_name = "influxdb-dev"
            self._instance_category = "database"

        self._aws_region = cmd_args.aws_region
        self._helm = HelmClient(aws_region=cmd_args.aws_region, cluster=cluster)
        self._cluster = cluster
        self._helm.check_cluster_connectivity()

    def _validate_orgs(self, orgs: list[str]) -> None:
        for org in orgs:
            if not self._ALLOWED_ORG_NAMES.fullmatch(org):
                raise ToolchainAssertion(f"Invalid org name: {org} (a-z, - allowed, length 4-15 characters)")

    def run(self) -> int:
        namespace = self._namespaces[0]
        self.install_influxdb(namespace)
        self.setup_influxdb_users(namespace)
        return 0

    def install_influxdb(self, namespace: str) -> ChartDeployResults:
        chart = HelmChart.for_path(self.LOCAL_CHART_PATH)
        self._helm.update_dependencies(chart.path)
        deploy_time = utcnow()
        _logger.info(f"Installing influxdb chart to {namespace}@{self._cluster.value}")
        values = self._get_values(chart, self._cluster)
        exec_result = self._helm.upgrade_install_from_local_path(
            release_name=self._release_name,
            namespace=namespace,
            chart_path=chart.path,
            values=values,
            install_timeout_sec=900,
        )

        deploy_result = ChartDeployResults.create(
            deployer=self._deployer, chart=chart, deploy_time=deploy_time, exec_result=exec_result
        )
        return deploy_result

    def _get_values(self, chart: HelmChart, cluster: KubernetesCluster) -> dict:
        values = chart.get_values()
        values["influxdb2"]["nodeSelector"]["toolchain.instance_category"] = self._instance_category
        values["influxdb2"]["persistence"]["size"] = "30Gi" if cluster.is_dev_cluster else "200Gi"
        return values

    def _get_admin_user(self) -> InfluxDBUser:
        accessor = KubernetesSecretsAccessor.create(namespace=self._namespaces[0], cluster=self._cluster)
        legacy_admin_secret = accessor.get_json_secret(self._LEGACY_MASTER_CREDS_SECRET_NAME)
        if legacy_admin_secret:
            # old installs, where the toolchain script generated the creds.
            # see: https://github.com/toolchainlabs/toolchain/pull/14053
            _logger.info(f"loaded influx admin from secret: {self._LEGACY_MASTER_CREDS_SECRET_NAME}")
            return InfluxDBUser.from_dict(legacy_admin_secret)
        # Generated by the influxdb2 chart.
        api = SecretAPI.for_cluster(namespace=self._namespaces[0], cluster=self._cluster)
        admin_creds = api.get_secret(self._MASTER_CREDS_SECRET_NAME)
        if not admin_creds:
            raise ToolchainAssertion("Can't determine influxdb admin creds")
        _logger.info(f"loaded influx admin from secret: {self._MASTER_CREDS_SECRET_NAME}")
        token = admin_creds["admin-token"].decode()
        password = admin_creds["admin-password"].decode()
        return InfluxDBUser(username="admin", token=token, password=password)

    def setup_influxdb_users(self, namespace: str) -> None:
        if not self._orgs:
            _logger.info("no org specified, skip user & orgs config.")
            return
        admin = self._get_admin_user()
        maybe_prompt_k8s_port_fwd(
            local_port=InfluxDBConnectionConfig.LOCAL_DEV_PORT,
            remote_port=80,
            namespace=namespace,
            prompt="InfluxDB needs to be accessible locally in order to finish setup. Please run:",
            service="influxdb",
            cluster=self._cluster,
        )
        for org in self._orgs:
            add_org(admin=admin, org_name=org)
            self._setup_users(admin=admin, org_name=org, override=self._override_users)

    def _setup_users(self, admin: InfluxDBUser, org_name: str, override: bool) -> None:
        self._setup_app_user(admin=admin, org_name=org_name, override=override)
        self._setup_app_readonly_user(admin=admin, org_name=org_name, override=override)
        self._setup_readonly_user(admin=admin, org_name=org_name, override=override)

    def _setup_app_user(self, admin: InfluxDBUser, org_name: str, override: bool) -> str:
        username = f"{org_name}-user-1"
        service_user, org_id = add_access_user(admin, org_name, username, override=override)
        if not service_user:  # User already exists
            _logger.info(f"app user {username} already exists.")
            return org_id
        self._save_app_user_secret(service_user=service_user, org_id=org_id, org_name=org_name, is_read_only=False)
        return org_id

    def _setup_app_readonly_user(self, admin: InfluxDBUser, org_name: str, override: bool) -> str:
        username = f"{org_name}-ro-user-1"
        service_user, org_id = add_access_user(admin, org_name, username, override=override)
        if not service_user:  # User already exists
            _logger.info(f"app user {username} already exists.")
            return org_id
        self._save_app_user_secret(service_user=service_user, org_id=org_id, org_name=org_name, is_read_only=True)
        return org_id

    def _save_app_user_secret(self, service_user: InfluxDBUser, org_id: str, org_name: str, is_read_only: bool) -> None:
        for namespace in self._namespaces:
            accessor = KubernetesSecretsAccessor.create_rotatable(namespace=namespace, cluster=self._cluster)
            buildsense_secret = {
                "token": service_user.token,
                "org_id": org_id,
            }
            secret_name = InfluxDBConnectionConfig.get_secret_name(org_name, is_read_only=is_read_only)
            accessor.set_secret(secret_name, json.dumps(buildsense_secret))
            _logger.info(f"Wrote token for {service_user.username} user into: {secret_name}@{namespace}")

    def _setup_readonly_user(self, admin: InfluxDBUser, org_name: str, override: bool) -> None:
        """Create a readonly user that can be used by non-toolchain code (like grafana)"""
        username = f"{org_name}-ro"
        user = add_readonly_user(admin, org_name, username, override=override)
        if not user:  # User already exists
            _logger.info(f"app read only user {username} already exists.")
            return
        secret_name = self.get_external_ro_user_secret_name(service=org_name)
        for ns in self._namespaces:
            accessor = KubernetesSecretsAccessor.create(namespace=ns, cluster=self._cluster)
            accessor.set_secret(secret_name, json.dumps(user.to_dict()))
            _logger.info(f"Wrote read only user details for {user.username} user into: {secret_name}@{ns}")

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        cls.add_aws_region_argument(parser)
        parser.add_argument(
            "--prod",
            action="store_true",
            required=False,
            default=False,
            help="Install & bootstrap on prod cluster",
        )
        parser.add_argument(
            "--namespace",
            type=str,
            action="store",
            default=None,
            help="namespace to install DB & secrets to (dev only)",
        )
        parser.add_argument(
            "--orgs",
            metavar="orgs",
            nargs="+",
            required=False,
            help="InfluxDB org names (InfluxDB org is like a relational database schama/namespace)",
        )
        parser.add_argument(
            "--override-users",
            action="store_true",
            required=False,
            default=False,
            help="Re-create users and their corresponding secrets",
        )


if __name__ == "__main__":
    InstallAndBootstrapInfluxDB.start()
