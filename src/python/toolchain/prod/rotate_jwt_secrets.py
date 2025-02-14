#!/usr/bin/env ./python
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import logging
from argparse import ArgumentParser, Namespace

from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.kubernetes.cluster import ClusterAPI
from toolchain.kubernetes.constants import KubernetesCluster, KubernetesProdNamespaces, get_namespaces_for_prod_cluster
from toolchain.prod.constants import JWKSET_SECRET_NAME
from toolchain.users.jwt.keys import JWTSecretData, JWTSecretKey
from toolchain.util.net.net_util import get_remote_username
from toolchain.util.secret.secrets_accessor import KubernetesSecretsAccessor, LocalSecretsAccessor

_logger = logging.getLogger(__name__)


class RotateJWTSecrets(ToolchainBinary):
    description = "Rotates JWT secrets"
    _JWT_SECRET_NAME = "jwt-auth-secret-key"
    _MAX_ACCESS_TOKEN_KEYS = 3

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._dry_run = cmd_args.dry_run
        self._update_only = cmd_args.update_only
        self._is_local = cmd_args.local
        if cmd_args.prod:
            if cmd_args.dev_namespace:
                raise ToolchainAssertion("Namespace can't be specified when working with prod cluster")
            self._master_cluster = KubernetesCluster.PROD
            self._remoting_cluster = KubernetesCluster.REMOTING
            self._main_namespace = KubernetesProdNamespaces.PROD
        elif not self._is_local:
            self._master_cluster = KubernetesCluster.DEV
            self._remoting_cluster = KubernetesCluster.DEV
            self._main_namespace = cmd_args.dev_namespace or get_remote_username()

    def check_cluster_connectivity(self) -> None:
        for cluster in [self._master_cluster, self._remoting_cluster]:
            ClusterAPI.is_connected_to_cluster(cluster)

    def run(self) -> int:
        if self._is_local:
            accessor = LocalSecretsAccessor.create_rotatable()
            accessor.set_secret(self._JWT_SECRET_NAME, json.dumps(JWTSecretData.create_new().to_dict()))
            return 0

        self.check_cluster_connectivity()
        current = self._read_current()
        if self._update_only:
            if not current:
                raise ToolchainAssertion("No current JWT key found")
            secret_data = current
        else:
            secret_data = self._generate_new_keys(current)
        self.update_secrets(secret_data)
        return 0

    def _generate_new_keys(self, current: JWTSecretData | None) -> JWTSecretData:
        # For now, supporting rotating access token keys.
        # support for rotating refresh token keys will be added in the future
        if current:
            current_access_token_keys = sorted(current.access_token_keys, key=lambda key: key.timestamp, reverse=True)
            refresh_token_keys = current.refresh_token_keys
        else:
            current_access_token_keys = []
            refresh_token_keys = (JWTSecretKey.create_new(short_key=True),)
        new_key = JWTSecretKey.create_new(short_key=True)
        _logger.info(
            f"Generated new access token JWT secret: {new_key.key_id} num of keys={len(current_access_token_keys)}"
        )
        access_token_keys = [new_key]
        access_token_keys.extend(current_access_token_keys)
        return JWTSecretData(
            refresh_token_keys=refresh_token_keys,
            access_token_keys=tuple(access_token_keys[: self._MAX_ACCESS_TOKEN_KEYS]),
        )

    def _read_current(self) -> JWTSecretData | None:
        accessor = KubernetesSecretsAccessor.create_rotatable(
            namespace=self._main_namespace, cluster=self._master_cluster
        )
        json_secret = accessor.get_json_secret(self._JWT_SECRET_NAME)
        return JWTSecretData.load(json_secret) if json_secret else None

    def update_secrets(self, jwt_data: JWTSecretData) -> None:
        jwk_set_json = json.dumps(jwt_data.get_access_tokens_jwk_set_dict())
        secret_json = json.dumps(jwt_data.to_dict())
        self._write_secrets(self._master_cluster, self._JWT_SECRET_NAME, secret_json)
        self._write_secrets(self._remoting_cluster, JWKSET_SECRET_NAME, jwk_set_json)

    def _write_secrets(self, cluster: KubernetesCluster, secret_name: str, secret_value: str) -> None:
        namespaces = (self._main_namespace,) if cluster.is_dev_cluster else get_namespaces_for_prod_cluster(cluster)
        for ns in namespaces:
            accessor = KubernetesSecretsAccessor.create_rotatable(namespace=ns, cluster=cluster)
            if accessor.get_secret(secret_name) == secret_value:
                continue
            _logger.info(f"set secret {secret_name} on {ns}@{cluster} dry_run={self._dry_run}")
            if not self._dry_run:
                accessor.set_secret(secret_name, value=secret_value)

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--update-only",
            action="store_true",
            required=False,
            default=False,
            help="Only update existing tokens, don't create new ones",
        )
        parser.add_argument("--dry-run", action="store_true", required=False, default=False, help="Dry run")
        parser.add_argument(
            "--prod",
            action="store_true",
            required=False,
            default=False,
            help="Ensure secrets on prod cluster (otherwise this will default to dev cluster)",
        )
        parser.add_argument("--dev-namespace", required=False, help="(dev only) - defaults current user's namespace.")
        parser.add_argument(
            "--local", action="store_true", required=False, default=False, help="Ensure JWT secret on local machine"
        )


if __name__ == "__main__":
    RotateJWTSecrets.start()
