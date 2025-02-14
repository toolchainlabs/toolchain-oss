# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from contextlib import contextmanager

import psycopg2

_postgres_creds_fields = {"user", "password", "host", "port", "dbname"}


class PostgresUtilBase:
    """A base class for classes that run setup or admin SQL statements on a Postgres instance.

    Subclass methods can access the database like this:

    with self.cursor() as cursor:  # psycopg cursor, see


    http://initd.org/psycopg/docs/
    for details.
      cursor.execute(sql, params)
      cursor.fetchone()
      ...

    Clients can create an instance and ensure the connection is closed like this:

    with Subclass.connect(**master_creds) as script:
      script.do_something()
      script.do_something_else()
      ...
    """

    CONNECTION_TIMEOUT_SECONDS = 3

    @classmethod
    @contextmanager
    def connect(cls, **master_creds):
        prc = cls(**master_creds)
        try:
            yield prc
        finally:
            prc.close()

    def __init__(self, **master_creds):
        """
        :param dict master_creds: Postgres creds for a role with sufficient privileges to execute the sql statements.
        """
        # We may add various custom creds fields for our own uses, so filter them out before passing them to psycopg2.
        filtered_master_creds = {k: v for k, v in master_creds.items() if k in _postgres_creds_fields}

        self._conn = psycopg2.connect(connect_timeout=self.CONNECTION_TIMEOUT_SECONDS, **filtered_master_creds)
        self._conn.autocommit = True  # Some DDL statements (e.g., CREATE/DROP DATABASE) error if run in a transaction.

    def close(self):
        self._conn.close()

    def cursor(self):
        return self._conn.cursor()
