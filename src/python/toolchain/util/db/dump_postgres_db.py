# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PostgresDBInfo:
    host: str
    port: int
    user: str
    password: str
    role: str
    db_name: str


class PostgresDbDumper:
    def __init__(self, db_info: PostgresDBInfo) -> None:
        self._db_info = db_info

    def dump_db(
        self, *, tables: tuple[str, ...], dump_filepath: str, dump_format: str, extra_args: tuple[str, ...] = tuple()
    ):
        # see https://www.postgresql.org/docs/11/app-pgdump.html
        tables_args = [f"--table={table}" for table in tables]
        base_args = [
            "-h",
            self._db_info.host,
            "-p",
            str(self._db_info.port),
            "-U",
            self._db_info.user,
            "--verbose",
            f"--role={self._db_info.role}",
            "--no-owner",
            f"--format={dump_format}",
            f"--file={dump_filepath}",
        ]
        base_args.extend(extra_args)

        cmd = ["pg_dump"] + base_args + tables_args + [self._db_info.db_name]
        cmd_str = " ".join(cmd)
        _logger.info(f"Dump DB: {cmd_str}")
        retries_left = 3
        while retries_left > 0:
            try:
                res = subprocess.run(cmd, check=True, env={"PGPASSWORD": self._db_info.password})
                _logger.info(f"pg_dump done: {res!r}")
                return
            except subprocess.CalledProcessError as error:
                output = ((error.stdout or b"") + (error.stderr or b"")).decode()
                _logger.warning(f"pg_dump failed: {output}")
                if "Temporary failure in name resolution" not in output:
                    raise
                time.sleep(4)
                retries_left -= 1
