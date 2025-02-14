# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
import textwrap

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.util.db.postgres_util_base import PostgresUtilBase

logger = logging.getLogger(__name__)


class PostgresDbCreator(PostgresUtilBase):
    """Create a postgres database."""

    CONNECTION_TIMEOUT_SECONDS = 10  # longer timeout since the DB might be starting up.

    def create_db_if_not_exists(self, dbname: str, owner: str) -> None:
        if self.db_owner(dbname) == owner:
            return
        elif self.db_exists(dbname):
            raise ToolchainAssertion(f"Database {dbname} exists but with unexpected owner {owner}")
        self.create_db(dbname, owner)

    def create_db(self, dbname: str, owner: str) -> None:
        create_db_sql = textwrap.dedent(
            f"""
            CREATE DATABASE {dbname}
            WITH OWNER {owner}
            ENCODING 'UTF-8'
            LC_COLLATE 'en_US.UTF-8'
            LC_CTYPE 'en_US.UTF-8'
            TEMPLATE template0
            """
        ).strip()
        # By default all users can connect to a new database. We revoke that privilege immediately.
        lock_down_db_sql = f"REVOKE CONNECT ON DATABASE {dbname} FROM PUBLIC"

        with self.cursor() as curs:
            curs.execute(create_db_sql)
            curs.execute(lock_down_db_sql)

        logger.info(f"Created db {dbname}")

    def db_exists(self, dbname: str) -> bool:
        db_exists_sql = "SELECT '1' FROM pg_catalog.pg_database WHERE datname=%s"
        with self.cursor() as curs:
            curs.execute(db_exists_sql, (dbname,))
            ret = curs.fetchone()
            return ret is not None

    def db_owner(self, dbname: str) -> str | None:
        db_owner_sql = textwrap.dedent(
            """
            SELECT pg_catalog.pg_get_userbyid(d.datdba) as "owner"
            FROM pg_catalog.pg_database d
            WHERE d.datname=%s
            """
        )
        with self.cursor() as curs:
            curs.execute(db_owner_sql, (dbname,))
            ret = curs.fetchone()
            if not ret:
                return None
            return ret[0]

    def drop_db(self, dbname: str) -> None:
        drop_db_sql = f"DROP DATABASE {dbname}"
        with self.cursor() as curs:
            curs.execute(drop_db_sql)
