# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import contextlib
import getpass
import logging
import socket
import subprocess
import textwrap
from pathlib import Path, PurePath
from tempfile import gettempdir, mkdtemp
from time import sleep

import psycopg2
from fasteners import InterProcessLock

from toolchain.base.toolchain_error import ToolchainAssertion

_logger = logging.getLogger(__name__)


class TestingDB:
    """Ensures that a transient local postgres instance for testing is running.

    A postgres instance may already exist from previous test run. If not, we will start one. Each test invocation uses
    its own logical database, so it's usually fine to run just one global physical testing database instance.
    """

    DEFAULT_HOST = "localhost"
    # Not the default postgres port, so the test db doesn't collide with a local dev db or some other
    # unrelated db.
    DEFAULT_PORT = 5433

    DB_HOST_PORT = [None, None]

    @classmethod
    def create(cls) -> TestingDB:
        # Note: postgres instance may already exist from previous test run. If not, we will start one.
        # Each test invocation uses its own database, so it's fine to run just one global testing instance.
        test_db = cls()
        test_db.ensure_running()
        cls.DB_HOST_PORT = [test_db.host, test_db.port]
        return test_db

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self._host = host
        self._port = port

    @property
    def host(self):
        return self._host

    @property
    def port(self):
        return self._port

    def ensure_running(self):
        _logger.info(f"Check if DB is running on {self.host}:{self.port}")
        if self._is_listening():
            _logger.info("Test DB running")
            return
        _logger.info("DB not running")
        # NB: we use an inter-process lock to avoid a race condition where multiple tests
        # try to create the physical database at the same time, which causes the setup to hang. The
        # physical database must be only set up once.
        lock_file_path = PurePath(gettempdir()) / f"{getpass.getuser()}_postgres_test_database_setup.lock"
        with InterProcessLock(lock_file_path.as_posix()):
            # We check if the database was set up by a prior process. Only the first process to acquire
            # the lock should call _setup().
            if self._is_listening():
                return
            self._setup()

    def _setup(self):
        # Note: For brevity, the stdout/stderr of both the initdb and postgres invocations are sent to /dev/null,
        # but you may want to disable that if debugging these invocations.
        pgsql_path = Path(mkdtemp(prefix="pgsqltmp"))
        _logger.info(f"Setting up test DB. {pgsql_path=}")
        subprocess.check_call(
            [
                "initdb",
                "--debug",
                "-U",
                "postgres",
                "-D",
                pgsql_path.as_posix(),
                "--encoding",
                "UTF-8",
                "--lc-collate",
                "en_US.UTF-8",
                "--lc-ctype",
                "en_US.UTF-8",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Allow the superuser to login without a password, for convenience in the usual case,
        # but require a password from all other roles, so that permissions-related tests are meaningful.
        (pgsql_path / "pg_hba.conf").write_text(
            textwrap.dedent(
                """
                    host   all  postgres  samehost  trust
                    host   all  all       samehost  password
                    """
            )
        )
        subprocess.Popen(  # pylint: disable=consider-using-with
            [
                "postgres",
                "-h",
                self.host,
                "-p",
                f"{self.port}",
                "-k",
                pgsql_path.as_posix(),
                "-D",
                pgsql_path.as_posix(),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _logger.info("Waiting for DB ready")
        for i in range(0, 25):
            if self._is_listening():
                conn = self._can_connect()
                _logger.info(f"DB listening after {i} attempts. can_connect={conn}")
                if conn:
                    break
            sleep(0.5)
        else:
            raise ToolchainAssertion(f"Postgres not listening on {self.host}:{self.port}")

    def _is_listening(self):
        with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.settimeout(1.0)
            ret = sock.connect_ex((self.host, self.port))
            return ret == 0

    def _can_connect(self) -> bool:
        try:
            with psycopg2.connect(connect_timeout=2):
                pass
        except psycopg2.OperationalError as error:
            return "the database system is starting up" not in str(error)
        return True
