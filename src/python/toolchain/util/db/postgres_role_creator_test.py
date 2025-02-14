# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import secrets
import string
from datetime import datetime, timedelta, timezone

import psycopg2
import pytest

from toolchain.conftest import testing_db_host_port
from toolchain.util.db.postgres_db_creator import PostgresDbCreator
from toolchain.util.db.postgres_role_creator import PostgresRoleCreator, RoleOptions


class TestPostgresRoleCreator:
    @staticmethod
    def _random_rolename() -> str:
        # Pick a random rolename, in case a previous run of this test fails to clean up after itself.
        # Note that postgres lower-cases the names on creation, but not on query, so we must select
        # all-lower-case names here.
        role_suffix = "".join([secrets.choice(string.ascii_lowercase) for _ in range(16)])
        return f"testrole_{role_suffix}"

    def test_create_role(self) -> None:
        host, port = testing_db_host_port()
        with PostgresRoleCreator.connect(host=host, port=port, dbname="postgres", user="postgres") as prc:
            # Create a couple of group roles, so we can test that we clone role assignments correctly.
            group_role_1 = self._random_rolename()
            group_role_2 = self._random_rolename()
            group_role_options = RoleOptions(
                SUPERUSER=False,
                CREATEDB=True,
                CREATEROLE=False,
                INHERIT=True,
                LOGIN=False,
                REPLICATION=False,
                BYPASSRLS=False,
                CONNECTION_LIMIT=-1,
                VALID_UNTIL=None,
                ROLES=[],
            )
            prc.create_role(role_options=group_role_options, rolename=group_role_1, password=None)
            prc.create_role(role_options=group_role_options, rolename=group_role_2, password=None)

            # Create a role to clone.
            orig_role = self._random_rolename()
            orig_options = RoleOptions(
                SUPERUSER=False,
                CREATEDB=True,
                CREATEROLE=False,
                INHERIT=True,
                LOGIN=True,
                REPLICATION=False,
                BYPASSRLS=False,
                CONNECTION_LIMIT=50,
                VALID_UNTIL=datetime.now(timezone.utc) + timedelta(days=100),
                ROLES=[group_role_1, group_role_2],
            )
            prc.create_role(role_options=orig_options, rolename=orig_role, password="testpass1")

            # Clone the role.
            cloned_role = self._random_rolename()
            prc.clone_role(orig_role, cloned_role, password="testpass2")

            # Get the clone's options.
            clone_options = prc.get_role_options(cloned_role)

            # Check that we cloned correctly.
            assert orig_options == clone_options

            # Drop the original role and check that it was indeed dropped.
            prc.drop_role(orig_role)
            assert prc.get_role_options(orig_role) is None

            # Drop the other roles, in dependency order, to clean up.
            prc.drop_role(cloned_role)
            prc.drop_role(group_role_2)
            prc.drop_role(group_role_1)

    def test_privilege_inheritance(self) -> None:
        # A postgres role that is an owner of a database has implicit privileges in that database.
        # This test verifies that login roles we create that are members of owner roles inherit
        # those implicit privileges.
        host, port = testing_db_host_port()
        master_creds = {"host": host, "port": port, "dbname": "postgres", "user": "postgres"}
        with PostgresRoleCreator.connect(**master_creds) as prc:
            # Create an non-login owner role for a new db.
            owner_role = self._random_rolename()
            owner_role_options = RoleOptions(
                SUPERUSER=False,
                CREATEDB=False,
                CREATEROLE=False,
                INHERIT=True,
                LOGIN=False,
                REPLICATION=False,
                BYPASSRLS=False,
                CONNECTION_LIMIT=-1,
                VALID_UNTIL=None,
                ROLES=[],
            )
            prc.create_role(role_options=owner_role_options, rolename=owner_role, password=None)

            # Create a db owned by this role.
            dbname = f"db_{owner_role}"
            with PostgresDbCreator.connect(**master_creds) as pdc:
                pdc.create_db(dbname, owner=owner_role)

            # Create a user role.
            user_role = self._random_rolename()
            user_pwd = "pwd1"
            user_role_options = RoleOptions(
                SUPERUSER=False,
                CREATEDB=False,
                CREATEROLE=False,
                INHERIT=True,
                LOGIN=True,
                REPLICATION=False,
                BYPASSRLS=False,
                CONNECTION_LIMIT=-1,
                VALID_UNTIL=None,
                ROLES=[],
            )
            prc.create_role(role_options=user_role_options, rolename=user_role, password=user_pwd)
            user_creds = {"host": host, "port": port, "dbname": dbname, "user": user_role, "password": user_pwd}

            # Verify that the user cannot connect to the db.
            with pytest.raises(psycopg2.OperationalError, match="User does not have CONNECT privilege."):
                psycopg2.connect(**user_creds)

            # Now add the user to the owner role.
            with psycopg2.connect(**master_creds) as conn, conn.cursor() as cur:
                cur.execute(f"GRANT {owner_role} TO {user_role}")

            # Verify that the user now can connect to the db, by inheriting the user role's privilege.
            psycopg2.connect(**user_creds)
