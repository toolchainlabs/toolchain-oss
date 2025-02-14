#!/usr/bin/env ./python
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
import time
from argparse import ArgumentParser, Namespace
from enum import Enum, unique

from toolchain.aws.rds import RDS
from toolchain.base.password import generate_password
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.prod.db_credentials_rotator.db_secrets_rotator import DatabaseSecretRotator
from toolchain.util.db.postgres_role_creator import PostgresRoleCreator
from toolchain.util.logging.config_helpers import configure_for_tool

logger = logging.getLogger(__name__)


@unique
class TargetMode(Enum):
    DEV = "dev"
    PROD = "prod"


class DatabaseCredentialsRotator(ToolchainBinary):
    POD_RECYCLE_INTERVAL_SECS = 30

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._region = cmd_args.aws_region
        self._namespace = cmd_args.namespace
        self._db_name = cmd_args.database
        self._new_db_host = cmd_args.db_host
        self._mode = TargetMode(cmd_args.env)
        logger.info(
            f"DatabaseCredentialsRotator: namespace={self._namespace} mode={self._mode} db={self._db_name} new_db_host={self._new_db_host}"
        )
        self._rotator = DatabaseSecretRotator(namespace=self._namespace, db_name=self._db_name)

    def run(self) -> int:
        success = self._rotator.check_current_credentials_for_db().is_completed
        if not success:
            # Current state is not consistent. Don't start rotation
            return -1

        self._update_secret()
        promoted = self._rotator.promote_proposed_to_current()
        rollout = self._rotator.check_current_credentials_for_db()
        logger.info(f"promoted={promoted} consistent={rollout.is_completed}")
        if rollout.is_completed:
            logger.warning("Pods states is consistent after new secret was promoted. This is unexpected.")
            return -1
        self._reach_consistency(rollout.total_pods)
        return 0

    def _reach_consistency(self, num_of_pods: int) -> bool:
        max_attempts = num_of_pods * 2
        counter = 0
        rotator = self._rotator
        while counter < max_attempts:
            counter += 1
            rollout = rotator.check_current_credentials_for_db()
            logger.info(
                f"count={counter}/{max_attempts} is_completed={rollout.is_completed} all_running={rollout.all_running}"
            )
            if rollout.is_completed:
                return True
            if rollout.all_running:
                self._rotator.kill_unmatched_pod(rollout)
            time.sleep(self.POD_RECYCLE_INTERVAL_SECS)
        return False

    def _update_secret(self) -> None:
        curr_creds = self._rotator.get_current_creds()
        if self._new_db_host:
            new_creds = self._update_host(self._new_db_host, curr_creds)
        else:
            new_creds = self._db_create_new_creds(self._db_name, curr_creds)
        self._rotator.propose_json_secret(new_creds)

    def _update_host(self, new_db_host: str, curr_creds: dict) -> dict:
        current_host = curr_creds.get("host")
        current_port = curr_creds.get("port")
        if not current_host or not current_port:
            raise ToolchainAssertion(f"Current host/port not specified in current secret. keys={curr_creds.keys()}")
        host, _, port = new_db_host.partition(":")
        port = port or current_port
        if not port or not host:
            raise ToolchainAssertion(f"Invalid host/port values provided: {new_db_host}")
        logger.info(f"Updating DB Host for {self._db_name} from {current_host}:{current_port} to {new_db_host}")
        curr_creds.update(host=host, port=int(port))
        return curr_creds

    def _get_master_creds(self, db_identifier: str) -> dict:
        if self._mode == TargetMode.PROD:
            rds_client = RDS(self._region)
            return rds_client.set_and_get_db_master_credentials(db_identifier)
        # else, dev
        return self._rotator.get_master_creds_in_dev()

    def _get_new_user_name(self, role_creator) -> str:
        index = 0
        while True:
            new_name = f"{self._db_name}_{index:04d}"
            if role_creator.get_role_options(new_name) is None:
                return new_name
            index += 1

    def _db_create_new_creds(self, db_name: str, curr_creds: dict) -> dict:
        master_creds = self._get_master_creds(db_name)
        mc = dict(master_creds)
        mc["password"] = mc["password"][:3]
        logger.info(f"connect to db {db_name}: {mc}")
        # patch creds for local-dev
        # master_creds.update(host="localhost", port=5435)
        role_creator = PostgresRoleCreator(**master_creds)
        new_user_name = self._get_new_user_name(role_creator)
        new_password = generate_password()
        role_creator.clone_role(curr_creds["user"], new_user_name, password=new_password, database=self._db_name)
        new_creds = dict(curr_creds)
        new_creds.update({"user": new_user_name, "password": new_password})
        logger.info(f"Created new creds for db={db_name} new_user_name={new_user_name}")
        return new_creds

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        parser.add_argument("--namespace", type=str, required=True, help="Namespace to rotate credentials in")
        parser.add_argument("--env", required=True, help="Environment (dev/prod).")
        parser.add_argument("--database", required=True, help="DB to rotate creds for.")
        parser.add_argument(
            "--db-host",
            required=False,
            type=str,
            default=None,
            help="New DB host (if specified, DB host will be update and rotated but not the db user).",
        )
        cls.add_aws_region_argument(parser)

    @classmethod
    def configure_logging(cls, log_level, use_colors=True):
        configure_for_tool(log_level)


if __name__ == "__main__":
    DatabaseCredentialsRotator.start()
