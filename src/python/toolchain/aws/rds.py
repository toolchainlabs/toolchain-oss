# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
import time
from dataclasses import dataclass
from enum import Enum, unique
from typing import cast

import botocore

from toolchain.aws.aws_api import AWSService
from toolchain.base.password import generate_password
from toolchain.base.toolchain_error import ToolchainAssertion

_logger = logging.getLogger(__name__)


@unique
class DatabaseType(Enum):
    INSTANCE = "instance"
    CLUSTER = "cluster"


@dataclass(frozen=True)
class DBInfo:
    cluster: str
    instance: str
    address: str
    port: int
    user: str


class RDS(AWSService):
    service = "rds"
    Type = DatabaseType

    def get_database_type(self, db_identifier: str) -> DatabaseType:
        # Order matters because in clusters include db instances.
        if self._get_cluster_info(db_identifier, raise_error=False):
            return DatabaseType.CLUSTER
        if self._get_instance_info(db_identifier, raise_error=False):
            return DatabaseType.INSTANCE
        raise ToolchainAssertion(f"Unknown DB with ID: {db_identifier}")

    def _get_instance_info(self, db_identifier: str, raise_error: bool = True) -> dict | None:
        try:
            db_instances = self.client.describe_db_instances(DBInstanceIdentifier=db_identifier)["DBInstances"]
        except botocore.exceptions.ClientError as error:
            if error.response["Error"]["Code"] == "DBInstanceNotFound":
                db_instances = []
            else:
                raise
        if not db_identifier and not raise_error:
            return None
        if len(db_instances) != 1:
            raise ToolchainAssertion(f"Unexpected number of DB instances for {db_identifier}")
        return db_instances[0]

    def get_db_instance_endpoint(self, db_identifier: str) -> tuple[str, int]:
        endpoint = self._get_instance_info(db_identifier)["Endpoint"]  # type: ignore
        return endpoint["Address"], endpoint["Port"]

    def get_db_endpoint(self, db_identifier: str, db_type: DatabaseType) -> tuple[str, int]:
        if db_type == DatabaseType.CLUSTER:
            return self.get_cluster_endpoint(db_identifier)
        if db_type == DatabaseType.INSTANCE:
            return self.get_db_instance_endpoint(db_identifier)
        raise ToolchainAssertion(f"Unexpected DB Type: {db_type}")

    def _get_cluster_info(self, db_cluster_identifier: str, raise_error: bool = True) -> dict | None:
        try:
            db_clusters = self.client.describe_db_clusters(DBClusterIdentifier=db_cluster_identifier)["DBClusters"]
        except botocore.exceptions.ClientError as error:
            if error.response["Error"]["Code"] != "DBClusterNotFoundFault":
                raise
            if raise_error:
                raise ToolchainAssertion(f"No cluster with ID: {db_cluster_identifier}")
            return None
        if len(db_clusters) != 1:
            raise ToolchainAssertion(f"Unexpected number of DB clusters for {db_cluster_identifier}")
        return db_clusters[0]

    def get_cluster_endpoint(self, db_cluster_identifier: str) -> tuple[str, int]:
        cluster = self._get_cluster_info(db_cluster_identifier)
        return cluster["Endpoint"], cluster["Port"]  # type: ignore

    def get_instance_status(self, db_identifier: str) -> str | None:
        info = self._get_instance_info(db_identifier)
        if not info:
            return None
        return info["DBInstanceStatus"]

    def _wait_for_instance_status(
        self, db_identifier: str, status: str, timeout_sec: int, raise_error: bool = True, interval_sec: float = 0
    ) -> None:
        wait_until = time.time() + timeout_sec
        start = time.time()
        first_status = ""
        while time.time() <= wait_until:
            curr_status = self.get_instance_status(db_identifier)
            first_status = first_status or curr_status  # type: ignore
            _logger.debug(f"status={curr_status} expected={status}")
            if status == curr_status:
                time_took = int(time.time() - start)
                _logger.info(f"{db_identifier} status change {first_status}->{curr_status} took: {time_took} seconds.")
                return
            time.sleep(interval_sec or 0.3)
        if raise_error:
            raise ToolchainAssertion(
                f"Instance {db_identifier} didn't reach desired status ({status}) within timeout. Instance status: {curr_status}"
            )

    def _wait_for_cluster_status(
        self, db_cluster_identifier: str, status: str, timeout_sec: int, raise_error: bool = True
    ) -> None:
        wait_until = time.time() + timeout_sec
        start = time.time()
        first_status = ""
        while time.time() <= wait_until:
            curr_status = self._get_cluster_info(db_cluster_identifier)["Status"]  # type: ignore
            first_status = first_status or curr_status
            _logger.debug(f"status={curr_status} expected={status}")
            if status == curr_status:
                time_took = int(time.time() - start)
                _logger.info(
                    f"{db_cluster_identifier} status change {first_status}->{curr_status} took: {time_took} seconds."
                )
                return
            time.sleep(0.7)
        if raise_error:
            raise ToolchainAssertion(
                f"Cluster {db_cluster_identifier} didn't reach desired status ({status}) within timeout. Cluster status: {curr_status}"
            )

    def modify_master_creds(self, db_identifier: str, db_type: DatabaseType, new_password: str) -> str:
        if db_type == DatabaseType.CLUSTER:
            return self._modify_cluster_master_creds(db_identifier, new_password)
        if db_type == DatabaseType.INSTANCE:
            return self._modify_instance_master_creds(db_identifier, new_password)
        raise ToolchainAssertion(f"Unexpected DB Type: {db_type}")

    def _modify_instance_master_creds(self, db_identifier: str, new_password: str) -> str:
        response = self.client.modify_db_instance(
            DBInstanceIdentifier=db_identifier, ApplyImmediately=True, MasterUserPassword=new_password
        )
        user = response["DBInstance"]["MasterUsername"]
        # It takes time until the instance enters resetting-master-credentials state.
        self._wait_for_instance_status(db_identifier, "resetting-master-credentials", timeout_sec=90, raise_error=False)
        self._wait_for_instance_status(db_identifier, "available", timeout_sec=180)
        return user

    def _modify_cluster_master_creds(self, db_cluster_identifier: str, new_password: str) -> str:
        response = self.client.modify_db_cluster(
            DBClusterIdentifier=db_cluster_identifier, ApplyImmediately=True, MasterUserPassword=new_password
        )
        user = response["DBCluster"]["MasterUsername"]
        self._wait_for_cluster_status(
            db_cluster_identifier, "resetting-master-credentials", timeout_sec=90, raise_error=False
        )
        self._wait_for_cluster_status(db_cluster_identifier, "available", timeout_sec=180)
        return user

    def _get_latest_snapshot_id(self, db_identifier: str, min_date: datetime.datetime) -> str:
        # todo: check for pagination
        snapshots = self.client.describe_db_cluster_snapshots(DBClusterIdentifier=db_identifier)["DBClusterSnapshots"]
        if not snapshots:
            raise ToolchainAssertion(f"No snapshots for {db_identifier}")
        last_snapshot = sorted(snapshots, key=lambda snapshot: snapshot["SnapshotCreateTime"], reverse=True)[0]
        snapshot_time = last_snapshot["SnapshotCreateTime"]
        if snapshot_time < min_date:
            raise ToolchainAssertion(f"Latest snapshot date={snapshot_time} is too old ({min_date=})")
        return last_snapshot["DBClusterSnapshotIdentifier"]

    def restore_last_snapshot(
        self, db_identifier: str, security_group_id: str, password: str, min_snapshot_date: datetime.datetime
    ) -> DBInfo:
        source_cluster = cast(dict, self._get_cluster_info(db_identifier))
        snapshot_id = self._get_latest_snapshot_id(db_identifier, min_snapshot_date)
        restored_db_identifier = f"{db_identifier}-0-restore"
        restored_db_cluster_identifier = f"{db_identifier}-restore"
        _logger.info(f"Resore {snapshot_id} into {restored_db_identifier}")
        restored_cluster = self.client.restore_db_cluster_from_snapshot(
            DBClusterIdentifier=restored_db_cluster_identifier,
            SnapshotIdentifier=snapshot_id,
            DBSubnetGroupName=source_cluster["DBSubnetGroup"],
            Engine=source_cluster["Engine"],
            EngineVersion=source_cluster["EngineVersion"],
            VpcSecurityGroupIds=[security_group_id],
            DeletionProtection=False,
        )["DBCluster"]

        self.client.create_db_instance(
            DBInstanceIdentifier=restored_db_identifier,
            DBInstanceClass="db.t3.medium",
            Engine=source_cluster["Engine"],
            EngineVersion=source_cluster["EngineVersion"],
            DBClusterIdentifier=restored_db_cluster_identifier,
        )
        self._wait_for_cluster_status(
            restored_db_cluster_identifier, status="available", timeout_sec=30 * 60, raise_error=True
        )
        self._wait_for_instance_status(
            restored_db_identifier, status="available", timeout_sec=10 * 60, raise_error=True
        )
        user = self._modify_cluster_master_creds(restored_db_cluster_identifier, new_password=password)
        db_info = DBInfo(
            cluster=restored_db_cluster_identifier,
            instance=restored_db_identifier,
            address=restored_cluster["ReaderEndpoint"],
            port=restored_cluster["Port"],
            user=user,
        )
        return db_info

    def delete_db_cluster(self, db_info: DBInfo) -> None:
        if not db_info.cluster.endswith("-restore") or not db_info.instance.endswith("-restore"):
            raise ToolchainAssertion("Only use this to delete DB Instances created from snapshots")
        _logger.info(f"Delete DB Instances: {db_info.instance} of {db_info.cluster}")
        self.client.delete_db_instance(DBInstanceIdentifier=db_info.instance, SkipFinalSnapshot=True)
        self.client.delete_db_cluster(DBClusterIdentifier=db_info.cluster, SkipFinalSnapshot=True)

    def set_and_get_db_master_credentials(self, db_identifier: str) -> dict:
        # This is hard coded to return a dict in what PostgresUtilBase classes expect.
        db_type = self.get_database_type(db_identifier)
        host, port = self.get_db_endpoint(db_identifier=db_identifier, db_type=db_type)
        master_password = generate_password()
        user = self.modify_master_creds(db_identifier=db_identifier, db_type=db_type, new_password=master_password)
        return {
            "engine": "postgres",
            "set_role": None,
            "dbname": "postgres",
            "user": user,
            "password": master_password,
            "host": host,
            "port": port,
        }
