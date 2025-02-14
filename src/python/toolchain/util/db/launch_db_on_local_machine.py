#!/usr/bin/env ./python
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import time
from argparse import ArgumentParser, Namespace
from pathlib import Path

from toolchain.base.password import generate_password
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.testing_db import TestingDB
from toolchain.util.db.db_secrets import DatabaseSecretsHelper
from toolchain.util.db.init_db import DbInitializer

logger = logging.getLogger(__name__)


class LaunchDbOnLocalMachine(ToolchainBinary):
    """Launch a db instance on the local machine.

    Assumes postgresql is installed on the local machine.
    """

    _default_dev_db_port = 5434

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._instance_name = cmd_args.instance_name
        base_location = Path(cmd_args.location) if cmd_args.location else Path.home()
        self._location = base_location / f"toolchain.{self._instance_name}.pgsql"
        self._dbs = cmd_args.db or []
        self._simple_dbs = cmd_args.simple_db
        secrets = DatabaseSecretsHelper.for_local()
        self._is_ci = "CI" in os.environ
        self._master_creds_secret_name = f"{self._instance_name}-master-creds"
        port = TestingDB.DEFAULT_PORT if self._is_ci else cmd_args.port
        self._master_creds = self._get_or_create_master_creds(secrets, port)
        self._initializer = DbInitializer(secrets, master_creds=self._master_creds)

    def run(self) -> int:
        if not self._is_ci:
            self.create_local_db_if_not_exists()
        self.init_local_db()
        logger.info("Done!")
        return 0

    def create_local_db_if_not_exists(self) -> None:
        if self._location.exists():
            try:
                subprocess.check_call(["pg_controldata", self._location.as_posix()], stdout=subprocess.DEVNULL)
                logger.info(f"Db already exists at {self._location}.")
                return
            except subprocess.CalledProcessError:
                logger.exception(
                    f"Data dir exists at {self._location}, but couldn't verify its validity. "
                    "If safe to do so, remove it and rerun this script to continue."
                )
                raise
        self.create_local_db()

    def create_local_db(self) -> None:
        logger.info(f"Creating postgresql db at {self._location}")
        # Note that NamedTemporaryFile is always created with permissions 0600.
        with tempfile.NamedTemporaryFile() as pwdfile:
            pwdfile.write(self._master_creds["password"].encode("utf8"))
            pwdfile.flush()
            cmd = [
                "initdb",
                self._location.as_posix(),
                "--username",
                self._master_creds["user"],
                "--pwfile",
                pwdfile.name,
                "--auth",
                "md5",
            ]
            subprocess.check_call(cmd, stdout=subprocess.DEVNULL)
        logger.info("Database creation complete.")

    def init_local_db(self) -> None:
        self.ensure_db_running()
        initializer = DbInitializer(DatabaseSecretsHelper.for_local(rotatable=False), master_creds=self._master_creds)
        for simple_db in self._simple_dbs:
            initializer.init_db_simple(db_release_name=self._instance_name, db_name=simple_db)
        for db in self._dbs:
            self._initializer.init_db(db_release_name=self._instance_name, db_name=db)
            logger.info(f"Database {db} initialized on {self._instance_name}.")

    def _get_or_create_master_creds(self, secrets: DatabaseSecretsHelper, port: int) -> dict:
        master_creds = secrets.get_db_creds(self._master_creds_secret_name)
        if master_creds is None:
            master_creds = self._create_master_creds(port)
            secrets.store_db_creds(self._master_creds_secret_name, master_creds)
        return master_creds

    @staticmethod
    def _create_master_creds(port: int) -> dict:
        password = generate_password()
        creds = {
            "engine": "postgres",
            "user": "postgres",
            "password": password,
            "set_role": None,
            "host": "localhost",
            "port": port,
            "dbname": "postgres",
        }
        return creds

    def ensure_db_running(self) -> None:
        if self._is_ci:
            TestingDB.create()
            return
        try:
            subprocess.check_call(["pg_ctl", "status", f"--pgdata={self._location}"])
            return
        except subprocess.CalledProcessError as error:
            logger.warning(f"pg_ctl status failed: {error!r}")
            self.start_db()
            # Should be enough to make sure the db is ready.  This is just a local dev setup script, so
            # polling for readiness is overkill (and not always possible, since the db sometimes restarts itself
            # soon after startup).
            time.sleep(5)

    def start_db(self) -> None:
        logfile = self._location.as_posix() + ".log"
        port = self._master_creds["port"]
        cmd = [
            "pg_ctl",
            "start",
            f"--pgdata={self._location}",
            f"--log={logfile}",
            "--wait",
            f'--options="-p {port}"',
            # N.B.: We turn off the postgres unix domain socket here with `-k ""` since we don't use it and creating
            # the socket file requires elevated permissions on linux. Using a blank directory for `-k` to achieve this
            # is documented under "unix_socket_directories" at
            # https://www.postgresql.org/docs/current/runtime-config-connection.html.
            # fmt: off
            '--options="-k \"\""',
            # fmt: on
        ]
        try:
            subprocess.check_call(cmd)
        except subprocess.CalledProcessError as error:
            cmd_line = " ".join(cmd)
            logger.warning(f"pg_ctl status failed: {error!r} {error.stdout=} {error.stderr=}")
            logger.warning(f"command line: {cmd_line}")
            raise

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--instance-name",
            metavar="name",
            required=True,
            help="The name of the db instance.  Used to qualify names of creds secrets.",
        )
        parser.add_argument("--location", metavar="<path>", default=None, help="Create data dir at this location.")
        parser.add_argument(
            "--port", metavar="<port>", type=int, default=cls._default_dev_db_port, help="Port to listen on."
        )
        parser.add_argument(
            "--db",
            metavar="<db_name>",
            action="append",
            help="Names of logical databases to create in the db instance.  "
            "Each db will have a corresponding owner role and login role.",
        )
        parser.add_argument(
            "--simple-db",
            metavar="<simple_db_name>",
            action="append",
            help="Names of logical databases to create in the db instance, simple DBs are created without role and with a non-rotatable json secret.",
        )


if __name__ == "__main__":
    LaunchDbOnLocalMachine.start()
