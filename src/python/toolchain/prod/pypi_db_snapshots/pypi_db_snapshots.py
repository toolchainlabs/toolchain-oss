# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime
import logging
import os
from argparse import ArgumentParser, Namespace

from toolchain.aws.ec2 import EC2
from toolchain.aws.rds import RDS
from toolchain.aws.s3 import S3
from toolchain.base.datetime_tools import utcnow
from toolchain.base.password import generate_password
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.util.db.dump_postgres_db import PostgresDbDumper, PostgresDBInfo
from toolchain.util.logging.config_helpers import configure_for_tool

_logger = logging.getLogger(__name__)


class PypiDBSnapshots(ToolchainBinary):
    # Needs to match tables in management/commands/restore_from_snapshot.py
    _TABLES = (
        "packagerepopypi_project",
        "packagerepopypi_release",
        "packagerepopypi_distribution",
        "packagerepopypi_distributiondata",
    )
    _ROLE = "pypi_owner"
    _BUCKET = "pypi-dev.us-east-1.toolchain.com"
    _DUMP_FILE = "/tmp/pypi_db.dump"
    _DEV_NODE_SECURITY_GROUP = "k8s.dev-e1-1.nodes"
    # Needs to match PREFIX in management/commands/restore_from_snapshot.py
    _TARGET_KEY_PREFIX = "shared/pypi_db_snapshots/"

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._aws_region = cmd_args.aws_region
        self._rds = RDS(self._aws_region)

    def run(self) -> int:
        dump_file = self._DUMP_FILE
        s3 = S3(self._aws_region)
        target_key = os.path.join(self._TARGET_KEY_PREFIX, f"pypi-db.{utcnow().date().isoformat()}.dump")
        if s3.exists(bucket=self._BUCKET, key=target_key):
            _logger.warning(f"Dumped DB for already exists: {target_key}")
            return 0
        restore_db_identifier = self._restore_db_and_dump_db(dump_file)
        _logger.info(f"Upload {dump_file} to s3://{self._BUCKET}/{target_key}")
        s3.upload_file(bucket=self._BUCKET, key=target_key, path=dump_file, content_type="binary/octet-stream")
        status = self._rds.get_instance_status(restore_db_identifier) or "N/A"
        _logger.info(f"Restore DB ({restore_db_identifier}) status: {status}")
        return 0

    def _restore_db_and_dump_db(self, dump_file) -> str:
        ec2 = EC2(self._aws_region)
        sg_id = ec2.get_security_group_id_by_name(self._DEV_NODE_SECURITY_GROUP)
        if not sg_id:
            raise ToolchainAssertion(f"Security group {self._DEV_NODE_SECURITY_GROUP} not found.")
        password = generate_password(length=12)
        min_date = utcnow() - datetime.timedelta(days=2)
        db_info = self._rds.restore_last_snapshot(
            db_identifier="pypi", security_group_id=sg_id, password=password, min_snapshot_date=min_date
        )
        self.dump_db(db_info, password, dump_file)
        self._rds.delete_db_cluster(db_info)
        return db_info.instance

    def dump_db(self, db_instance_info, password, dump_filepath) -> None:
        db_info = PostgresDBInfo(
            host=db_instance_info.address,
            port=db_instance_info.port,
            user=db_instance_info.user,
            password=password,
            role=self._ROLE,
            db_name="pypi",
        )
        dumper = PostgresDbDumper(db_info)
        # See https://www.postgresql.org/docs/11/app-pgdump.html
        dumper.dump_db(
            tables=self._TABLES, dump_filepath=dump_filepath, dump_format="custom", extra_args=("--data-only",)
        )

    @classmethod
    def configure_logging(cls, log_level, use_colors=True) -> None:
        configure_for_tool(log_level)

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        cls.add_aws_region_argument(parser)


if __name__ == "__main__":
    PypiDBSnapshots.start()
