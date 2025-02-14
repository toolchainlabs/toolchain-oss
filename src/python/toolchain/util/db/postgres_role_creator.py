# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
import textwrap
from dataclasses import astuple, dataclass, fields
from datetime import date

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.util.db.postgres_util_base import PostgresUtilBase

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RoleOptions:
    """A data class of postgres role creation options."""

    SUPERUSER: bool
    CREATEDB: bool
    CREATEROLE: bool
    INHERIT: bool
    LOGIN: bool
    REPLICATION: bool
    BYPASSRLS: bool
    CONNECTION_LIMIT: int
    VALID_UNTIL: date | None
    ROLES: list[str]

    @classmethod
    def get_login_role_options(cls, owner_role_name: str) -> RoleOptions:
        return cls(
            SUPERUSER=False,
            CREATEDB=False,
            CREATEROLE=False,
            INHERIT=False,
            LOGIN=True,
            REPLICATION=False,
            BYPASSRLS=False,
            CONNECTION_LIMIT=-1,
            VALID_UNTIL=None,
            ROLES=[owner_role_name],
        )

    @classmethod
    def get_owner_role_options(cls, login: bool = False) -> RoleOptions:
        return cls(
            SUPERUSER=False,
            CREATEDB=False,
            CREATEROLE=False,
            INHERIT=False,
            LOGIN=login,
            REPLICATION=False,
            BYPASSRLS=False,
            CONNECTION_LIMIT=-1,
            VALID_UNTIL=None,
            ROLES=[],
        )

    def get_sql(self):
        option_specs = []
        bool_fields = [field.name for field in fields(self) if field.type == "bool"]
        for field_name, val in zip(bool_fields, astuple(self)):
            val_str = "" if val else "NO"
            option_specs.append(f"{val_str}{field_name}")
        if self.CONNECTION_LIMIT != -1:
            option_specs.append(f"CONNECTION LIMIT {self.CONNECTION_LIMIT}")
        if self.VALID_UNTIL:
            option_specs.append(f"VALID UNTIL '{self.VALID_UNTIL.isoformat()}'")
        if self.ROLES:
            roles_str = ",".join(self.ROLES)
            option_specs.append(f"IN ROLE {roles_str}")
        return "\n".join(option_specs)


class PostgresRoleCreator(PostgresUtilBase):
    """Create a postgres role, possibly based on an existing role.

    Note that DDL statements shouldn't be parameterized (e.g., a parameterized "DROP ROLE %s" would generate "DROP ROLE
    'rolename'" whereas the DDL command is "DROP ROLE rolename", without quotes).

    Note that in Postgres roles can be assigned to other roles, and a "user" is just a role with a password and the
    LOGIN option.
    """

    # Since this code runs at after db server init and we want to give the DB more time to start
    CONNECTION_TIMEOUT_SECONDS = 20

    def clone_role(
        self, src_rolename: str, rolename: str, password: str | None = None, database: str | None = None
    ) -> None:
        """Creates a role with the same options as a given source role.

        If the source role is a login role, then the new role will use the given password. Otherwise password must not
        be specified.

        This method does not grant specific table/schema privileges to the new role, regardless of any such privileges
        the existing role may have. However it does assign to the new role all roles that were assigned to the existing
        role. This supports a model in which users never have directly-granted privileges, but instead privileges are
        granted to an underlying non-user role, which is then assigned to users that need those privileges. Under such a
        model this class will create a new user with identical access to the existing one.
        """
        role_options = self.get_role_options(src_rolename)
        if not role_options:
            raise ToolchainAssertion(f"Can't find role: {src_rolename} to clone.")
        self.create_role(role_options, rolename, password)
        if role_options.LOGIN and database:
            self.grant_connect(database=database, rolename=rolename)

    def create_role_if_not_exists(
        self,
        role_options: RoleOptions,
        rolename: str,
        password: str | None = None,
        database: str | None = None,
        grant_connect: bool = True,
    ) -> None:
        """Creates a role with the same if it doesn't already exists.

        If a the LOGIN option and a password & database are specified, this method will also grant connect permissions
        to the database. Unless, grant_connect is set to False. This is useful when trying to create an owner role and
        will also need to be able to login to the database. In those cases, the user must be created first, then the
        database (since the db owner must be specified during db creation) and only then the user can be granted
        permissions to connect to the db.
        """
        if grant_connect and role_options.LOGIN and not database:
            raise ToolchainAssertion("Must specify a database when role option LOGIN is enabled.")
        if role_options.LOGIN and not password:
            raise ToolchainAssertion("Must specify a password when role option LOGIN is enabled.")
        existing_role_options = self.get_role_options(rolename)
        if existing_role_options is None:
            self.create_role(role_options, rolename, password)
        elif role_options == existing_role_options:
            if role_options.LOGIN and password:
                self.set_password(rolename, password)
            logger.info(f"Role {rolename} already exists with the given options and password.")
        else:
            raise ToolchainAssertion(f"Role {rolename} exists but with unexpected options {existing_role_options}")
        if role_options.LOGIN and database and grant_connect:
            self.grant_connect(database=database, rolename=rolename)
            if password:
                self.set_password(rolename, password)

    def create_role(self, role_options: RoleOptions, rolename: str, password: str | None = None) -> None:
        """Creates a role with the given options and, optionally, password.

        The password must be provided iff role_options.LOGIN is True.
        """
        if password and not role_options.LOGIN:
            raise ToolchainAssertion("Cannot create a user with the NOLOGIN option.")
        if role_options.LOGIN and not password:
            raise ToolchainAssertion("Cannot create a user without a password.")
        role_options_sql = role_options.get_sql()
        create_user_sql = textwrap.dedent(
            f"""
      CREATE ROLE {rolename} WITH
      {role_options_sql}
    """
        ).strip()
        if password:
            create_user_sql += f"\nENCRYPTED PASSWORD '{password}'"

        with self.cursor() as curs:
            curs.execute(create_user_sql)

        logger.info(f"Created role {rolename} with {role_options}")

    def grant_role_to_user(self, role: str, user: str) -> None:
        """Grants role access to a user.

        This is used w/ postgres RDS where we need to grant the master user access to the DB owner role.
        Without this grant the master user won't be able to create a DB that the owner_role owns.
        More: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Appendix.PostgreSQL.CommonDBATasks.html#Appendix.PostgreSQL.CommonDBATasks.Roles
        """
        grant_role_sql = f"GRANT {role} TO {user}"
        with self.cursor() as curs:
            curs.execute(grant_role_sql)

    def grant_public_schema_access(self, role: str) -> None:
        """Grants the user access to the public schema of the DB.

        This is required for Postgresql v15 and above since this version will not allow this kind of access (specifially
        to create tables) by default. More info: https://www.postgresql.org/docs/release/15.0/ `Remove PUBLIC creation
        permission on the public schema (Noah Misch)`
        """
        grant_role_sql = f"GRANT ALL ON SCHEMA public TO {role}"
        logger.info(f"Grant {role} access to public schema")
        with self.cursor() as curs:
            curs.execute(grant_role_sql)

    def drop_role(self, rolename: str) -> None:
        """Drops the role if it exists."""
        drop_role_sql = f"DROP ROLE {rolename}"
        with self.cursor() as curs:
            curs.execute(drop_role_sql)
        logger.info(f"Dropped role {rolename}")

    def set_password(self, rolename: str, password: str) -> None:
        set_password_sql = f"ALTER ROLE {rolename} WITH ENCRYPTED PASSWORD '{password}'"
        with self.cursor() as curs:
            curs.execute(set_password_sql)
        logger.info(f"Set password for existing role {rolename}")

    def grant_connect(self, database: str, rolename: str) -> None:
        grant_connect_sql = f"GRANT CONNECT ON DATABASE {database} TO {rolename}"
        with self.cursor() as curs:
            curs.execute(grant_connect_sql)
        logger.info(f"Granted connect privileges on {database} to {rolename}")

    def get_role_options(self, rolename: str) -> RoleOptions | None:
        """Gets the options for the given role, or None if no such role exists.

        :rtype: RoleOptions
        """
        get_role_options_sql = textwrap.dedent(
            """
            SELECT r.rolsuper, r.rolcreatedb, r.rolcreaterole, r.rolinherit, r.rolcanlogin,
                   r.rolreplication, r.rolbypassrls, r.rolconnlimit, r.rolvaliduntil,
                   ARRAY(SELECT b.rolname
                         FROM pg_catalog.pg_auth_members m
                         JOIN pg_catalog.pg_roles b ON (m.roleid = b.oid)
                         WHERE m.member = r.oid) as memberof
            FROM pg_catalog.pg_roles r
            WHERE r.rolname = %s;
            """
        ).strip()
        with self.cursor() as curs:
            curs.execute(get_role_options_sql, (rolename,))
            row = curs.fetchone()
            return RoleOptions(*row) if row else None
