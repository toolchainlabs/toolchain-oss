#!/usr/bin/env ./python
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
from argparse import ArgumentParser, Namespace

from toolchain.aws.rds import RDS
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.kubernetes.cluster import ClusterAPI
from toolchain.kubernetes.constants import KubernetesCluster, KubernetesProdNamespaces, get_namespaces_for_prod_cluster
from toolchain.util.db.db_secrets import DatabaseSecretsHelper, SimpleDatabaseSecretsHelper
from toolchain.util.db.init_db import DbInitializer
from toolchain.util.prod.exceptions import NotConnectedToClusterError

logger = logging.getLogger(__name__)


class InitProductionDatabase(ToolchainBinary):
    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._db_cluster = self._get_db_cluster_name(cmd_args)
        self._db_name = self._get_db_name(cmd_args)
        self._rds_client = RDS(cmd_args.aws_region)
        self._cluster = KubernetesCluster(cmd_args.cluster)
        self._is_simple_db = cmd_args.simple_db
        self._check_only = cmd_args.check_connection

    def _get_db_cluster_name(self, cmd_args: Namespace) -> str:
        if cmd_args.use_shared_db:
            if cmd_args.db_cluster:
                raise ToolchainAssertion("--db-cluster cannot be specified when using --use-shared-db")
            return "shared"

        if not cmd_args.db_cluster:
            raise ToolchainAssertion("Must specify --db-cluster")

        return cmd_args.db_cluster

    def _get_db_name(self, cmd_args: Namespace) -> str:
        if cmd_args.db_name:
            return cmd_args.db_name
        if cmd_args.db_cluster:
            return cmd_args.db_cluster.replace("-", "_")
        raise ToolchainAssertion("Can't determine DB name, either --db-cluster or --db-name must be specified")

    def run(self) -> int:
        logger.info(f"Check connectivity: {self._cluster.value}")
        if not ClusterAPI.is_connected_to_cluster(self._cluster):
            raise NotConnectedToClusterError(self._cluster)

        namespaces = get_namespaces_for_prod_cluster(self._cluster)
        db_initializer = self._get_db_initlizer(self._is_simple_db, k8s_namespaces=namespaces)
        if self._check_only:
            db_initializer.check_connection()
            return 0

        if self._is_simple_db:
            db_initializer.init_db_simple(db_release_name=self._db_cluster, db_name=self._db_name)
        else:
            self._init_toolchain_db(db_initializer, k8s_namespaces=namespaces)
        return 0

    def _get_db_initlizer(self, is_simple: bool, k8s_namespaces: tuple[str, ...]) -> DbInitializer:
        secets_cls = SimpleDatabaseSecretsHelper
        if is_simple:
            prod_secrets = SimpleDatabaseSecretsHelper.for_kubernetes(cluster=self._cluster, namespaces=k8s_namespaces)
        else:
            prod_secrets = DatabaseSecretsHelper.for_kubernetes(  # type: ignore[assignment]
                namespace=KubernetesProdNamespaces.PROD, cluster=self._cluster
            )
        master_creds = self._rds_client.set_and_get_db_master_credentials(self._db_cluster)
        prod_secrets = secets_cls.for_kubernetes(cluster=self._cluster, namespaces=k8s_namespaces)  # type: ignore[attr-defined]
        return DbInitializer(prod_secrets, master_creds=master_creds, is_aws_rds=True)

    def _init_toolchain_db(self, db_initializer: DbInitializer, k8s_namespaces: tuple[str, ...]) -> None:
        # in Postgres RDS, the master user must be granted the db owner role in order to be able to create the DB.
        # https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Appendix.PostgreSQL.CommonDBATasks.html#Appendix.PostgreSQL.CommonDBATasks.Roles
        owner_role_name = db_initializer.create_db_and_owner(self._db_name, grant_to_master=True)
        for namespace in k8s_namespaces:
            helper = DatabaseSecretsHelper.for_kubernetes(namespace=namespace, cluster=self._cluster)
            initializer = DbInitializer(helper, master_creds=db_initializer.master_creds)
            login_role_name = f"{self._db_name}_{namespace}_0000"
            release_name = f"{namespace}-db"
            initializer.create_login_role(
                login_role_name,
                release_name=release_name,
                db_name=self._db_name,
                owner_role_name=owner_role_name,
                override_creds=True,
            )
        logger.info(
            f"Database {self._db_name} on {self._db_cluster} initialized for Kubernetes {self._cluster.value} cluster."
        )

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        cls.add_aws_region_argument(parser)
        parser.add_argument(
            "--db-cluster",
            metavar="<db_cluster_name>",
            required=False,
            help="Database Cluster name (and db name if --db-name is not specified).",
        )
        parser.add_argument(
            "--db-name",
            metavar="<db_name>",
            required=False,
            help="Database name, defeaults to the value of --db-cluster if not spcfied, must be specfied when using --use-shared-db",
        )
        parser.add_argument(
            "--cluster", action="store", default=KubernetesCluster.PROD.value, help="Kubernetes cluster"
        )
        parser.add_argument(
            "--use-shared-db", action="store_true", required=False, default=False, help="Use the shared RDS Cluster"
        )
        parser.add_argument(
            "--simple-db",
            action="store_true",
            required=False,
            default=False,
            help="Use simple DB config (no rotating users/secrets for DB",
        )
        parser.add_argument(
            "--check-connection",
            action="store_true",
            required=False,
            default=False,
            help="Just check the ability to connect to the DB without initlizing it.",
        )


if __name__ == "__main__":
    InitProductionDatabase.start()
