#!/usr/bin/env ./python
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from argparse import ArgumentParser, Namespace
from pathlib import Path

from toolchain.aws.rds import RDS
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.util.db.dump_postgres_db import PostgresDbDumper, PostgresDBInfo

_logger = logging.getLogger(__name__)


class ExportPostgresDB(ToolchainBinary):
    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        _logger.info(f"Export postgres DB: {cmd_args}")
        self._dest = Path(cmd_args.dest)
        if not self._dest.is_file():
            raise ToolchainAssertion(f"Not a file path: {cmd_args.dest}")
        self._dest.parent.mkdir(parents=True, exist_ok=True)
        self._db_identifier = cmd_args.name
        self._rds_client = RDS(cmd_args.aws_region)

    def run(self) -> int:
        db_name = self._db_identifier.replace("-", "_")
        master_creds = self._rds_client.set_and_get_db_master_credentials(self._db_identifier)
        db_info = PostgresDBInfo(
            host=master_creds["host"],
            port=master_creds["port"],
            user=master_creds["user"],
            password=master_creds["password"],
            role=f"{db_name}_owner",
            db_name=db_name,
        )
        dumper = PostgresDbDumper(db_info)
        dumper.dump_db(tables=tuple(), dump_filepath=self._dest.as_posix(), dump_format="plain")
        return 0

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        cls.add_aws_region_argument(parser)
        parser.add_argument("--dest", required=True, help="Dump file path")
        parser.add_argument(
            "--name",
            metavar="<db_name>",
            required=True,
            help="Name of DB Cluster or instance (should match the application logical name, i.e. users, buildsense, etc..)",
        )


if __name__ == "__main__":
    ExportPostgresDB.start()
