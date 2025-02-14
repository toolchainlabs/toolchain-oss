# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import secrets
import string

from toolchain.conftest import testing_db_host_port
from toolchain.util.db.postgres_db_creator import PostgresDbCreator


class TestPostgresDbCreator:
    @staticmethod
    def _random_db() -> str:
        # Pick a random db name, in case a previous run of this test fails to clean up after itself.
        random_db_name = "".join([secrets.choice(string.ascii_lowercase) for _ in range(16)])
        return f"testdb_{random_db_name}"

    def test_db_creation(self) -> None:
        host, port = testing_db_host_port()
        with PostgresDbCreator.connect(host=host, port=port, dbname="postgres", user="postgres") as pdc:
            dbname = self._random_db()
            assert not pdc.db_exists(dbname)
            assert pdc.db_owner(dbname) is None
            pdc.create_db(dbname, owner="postgres")
            assert pdc.db_exists(dbname)
            assert pdc.db_owner(dbname) == "postgres"
            pdc.drop_db(dbname)
            assert not pdc.db_exists(dbname)
            assert pdc.db_owner(dbname) is None
