# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from functools import cached_property

from toolchain.base.password import generate_password
from toolchain.util.db.postgres_db_creator import PostgresDbCreator
from toolchain.util.db.postgres_role_creator import PostgresRoleCreator, RoleOptions
from toolchain.util.db.postgres_util_base import PostgresUtilBase

logger = logging.getLogger(__name__)


class DbInitializer:
    """Utilities to set up a new db."""

    def __init__(self, secrets_helper, master_creds: dict, is_aws_rds: bool = False) -> None:
        self._secrets_helper = secrets_helper
        self._master_creds = master_creds
        self._is_aws_rds = is_aws_rds

    @cached_property
    def _role_creator(self) -> PostgresRoleCreator:
        return PostgresRoleCreator(**self._master_creds)

    @cached_property
    def _db_creator(self) -> PostgresDbCreator:
        return PostgresDbCreator(**self._master_creds)

    def get_role_creator_on_db(self, db_name: str) -> PostgresRoleCreator:
        creds = dict(**self.master_creds)
        creds["dbname"] = db_name
        return PostgresRoleCreator(**creds)

    @property
    def master_creds(self) -> dict:
        return self._master_creds

    @property
    def _db_host(self) -> str:
        return self._master_creds.get("original_host", self._master_creds["host"])

    @property
    def _db_port(self) -> int:
        return self._master_creds.get("original_port", self._master_creds["port"])

    @property
    def _db_server(self) -> str:
        return f"{self._db_host}:{self._db_port}"

    def check_connection(self) -> None:
        util = PostgresUtilBase(**self._master_creds)
        logger.info(f"Check connection to: {self._db_server}")
        with util.cursor() as cursor:
            cursor.execute("SELECT * FROM pg_stat_activity;")
        logger.info(f"connection to: {self._db_server} successful.")

    def init_db_simple(self, *, db_release_name: str, db_name: str) -> str:
        """Create a DB & a DB user without adding the set role logic.

        This is used for DBs that are being used by non toolchain software.
        """
        db_name = db_name.replace("-", "_")
        username = db_name  # for now
        password = generate_password()
        owner_role_opts = RoleOptions.get_owner_role_options(login=True)
        self._role_creator.create_role_if_not_exists(
            role_options=owner_role_opts,
            rolename=username,
            grant_connect=False,
            password=password,
        )
        if self._is_aws_rds:
            # When using RDS, the user issuing the CREATE DATABASE must be a member of the role that will be the owner of the database.
            # https://stackoverflow.com/a/34898033
            self._role_creator.grant_role_to_user(role=username, user=self._master_creds["user"])
        self._db_creator.create_db_if_not_exists(db_name, username)
        self._role_creator.grant_connect(database=db_name, rolename=username)
        logger.info(f"Simple DB {db_name} created. user/role {username}")
        secret_name = f"{db_release_name}-{db_name}".replace("_", "-")
        self._store_simple_db_creds(secret_name=secret_name, db_name=db_name, username=username, password=password)
        return secret_name

    def _store_simple_db_creds(self, secret_name: str, db_name: str, username: str, password) -> None:
        # Storing value in various format in the k8s secret so they can mounted into the pod that needs DB access in whatever way the software expects it.
        simple_db_creds = {
            "postgres-password": password,
            "postgres-user": username,
            "connection-string": f"postgresql://{username}:{password}@{self._db_server}/{db_name}",
        }
        self._secrets_helper.store_db_creds(secret_name, simple_db_creds)

    def init_db(self, db_release_name: str, db_name: str) -> None:
        """Create or update a database, owner role and login role, using the given admin creds.

        :param db_release_name: The name of the database chart helm release name. Based on the namespace, e.g. benjy-db, schmitt-db, etc...
        :param db_name: The name of the logical db to create.
        """
        db_name = db_name.replace("-", "_")
        owner_role_name = self.create_db_and_owner(db_name)

        # The login role is used just for logging in, and is rotated periodically. After login we call
        # SET ROLE to assume the owner role, so that any new objects we create are owned by that long-lived role
        # and not by the transient login role (we set INHERIT=False so the login role can't access the db
        # without SET ROLE).
        # In practice we use the DjangoPostgreSQLSetRoleApp to automate those SET ROLE calls.
        login_role_name = f"{db_name}_0000"  # When rotating creds we can increment the suffix.
        self.create_login_role(
            login_role_name, release_name=db_release_name, db_name=db_name, owner_role_name=owner_role_name
        )

    def create_db_and_owner(self, db_name: str, grant_to_master: bool = False) -> str:
        # The owner role is long-lived, and owns all the objects in the database.
        owner_role_name = f"{db_name}_owner"
        owner_role_opts = RoleOptions.get_owner_role_options()

        self._role_creator.create_role_if_not_exists(role_options=owner_role_opts, rolename=owner_role_name)
        if grant_to_master:
            self._role_creator.grant_role_to_user(role=owner_role_name, user=self._master_creds["user"])

        self._db_creator.create_db_if_not_exists(db_name, owner_role_name)
        self.get_role_creator_on_db(db_name).grant_public_schema_access(owner_role_name)
        return owner_role_name

    def create_login_role(
        self, login_role_name: str, release_name: str, db_name: str, owner_role_name: str, override_creds: bool = False
    ) -> None:
        # We created the login role with INHERIT=False, so it can only act as the owner role by issuing SET ROLE.
        # However to do this it needs to connect, so it must have explicit connect privileges to the db.
        # role_creator.create_role_if_not_exists grants connect to the role when LOGIN=True
        login_role_opts = RoleOptions.get_login_role_options(owner_role_name)
        secret_name = f"{release_name}-{db_name}-creds".replace("_", "-")
        creds = self.store_db_creds(
            secret_name=secret_name,
            db_name=db_name,
            role=owner_role_name,
            username=login_role_name,
            override_creds=override_creds,
        )

        self._role_creator.create_role_if_not_exists(
            role_options=login_role_opts, rolename=login_role_name, database=db_name, password=creds["password"]
        )

    def store_db_creds(
        self, secret_name: str, db_name: str, username: str, role: str | None = None, override_creds: bool = False
    ) -> dict:
        # Do we already have creds? If so reuse them.
        creds = self._secrets_helper.get_db_creds(secret_name)
        if override_creds or creds is None:
            creds = {
                "engine": "postgres",
                "user": username,
                "password": generate_password(),
                "host": self._db_host,
                "port": self._db_port,
                "dbname": db_name,
            }
            if role:
                creds["set_role"] = role
            self._secrets_helper.store_db_creds(secret_name, creds)
            logger.info(f"Created new creds at {secret_name} {username=} {db_name=}")
        else:
            logger.info(f"Using existing creds at {secret_name}")
        return creds
