#!/usr/bin/env ./python
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import base64
import inspect
import json
import logging
from argparse import ArgumentParser, Namespace
from collections.abc import Sequence
from typing import Callable

from django.utils.crypto import get_random_string

from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.kubernetes.constants import KubernetesCluster, get_namespaces_for_prod_cluster
from toolchain.toolshed.config import DuoAuthConfig
from toolchain.util.net.net_util import get_remote_username
from toolchain.util.secret.secrets_accessor import (
    AWSSecretsAccessor,
    KubernetesSecretsAccessor,
    LocalSecretsAccessor,
    SecretsAccessor,
)

logger = logging.getLogger(__name__)

ValueGenerator = Callable[[], str]


class SecretsAccessHelper:
    @classmethod
    def for_local(cls) -> SecretsAccessHelper:
        return cls(rotatable_accessors=(LocalSecretsAccessor.create_rotatable(),), accessors=(LocalSecretsAccessor(),))

    @classmethod
    def for_k8s_namespaces(cls, cluster: KubernetesCluster, namespaces: Sequence[str]) -> SecretsAccessHelper:
        rotatable_accessors = tuple(
            KubernetesSecretsAccessor.create_rotatable(ns, cluster=cluster) for ns in namespaces
        )
        accessors = tuple(KubernetesSecretsAccessor.create(ns, cluster=cluster) for ns in namespaces)
        return cls(rotatable_accessors=rotatable_accessors, accessors=accessors)

    def __init__(self, rotatable_accessors: Sequence[SecretsAccessor], accessors: Sequence[SecretsAccessor]):
        self._rotatable_accessors = rotatable_accessors
        self._accessors = accessors

    def get_value_and_accessor(self, secret_name: str, rotatable: bool) -> tuple[str, SecretsAccessor] | None:
        accessors = self._rotatable_accessors if rotatable else self._accessors
        for accessor in accessors:
            # Trying to find if the secret is defined in a specified namespace (precedence order is the order namespace specified in the command line).
            secret_value = accessor.get_secret(secret_name)
            if secret_value:
                return secret_value, accessor
        return None

    def set_secret(self, secret_name: str, secret_value: str, dry_run: bool, rotatable: bool) -> None:
        accessors = self._rotatable_accessors if rotatable else self._accessors
        for accessor in accessors:
            logger.info(f"Set secret {secret_name} on {accessor!r} dry run: {dry_run}")
            if dry_run:
                continue
            accessor.set_secret(secret_name, secret_value)


class EnsureSecrets(ToolchainBinary):
    description = "Ensure that common, useful secrets (not including database creds) exist in the given environment."
    _GITHUB_APP_CREDS_DEV = "github-dev-app-creds"
    _GITHUB_APP_CREDS_PROD = "github-prod-app-creds"
    _BITBUCKET_DEV = "bitbucket/dev"
    _BITBUCKET_PROD = "bitbucket/prod"
    _DUO_WEB_APP_PROD = "duo-toolshed-web-app-prod"
    _DUO_WEB_APP_DEV = "duo-toolshed-dev-web-app"
    _STRIPE_PROD = "stripe-integration-prod"
    _STRIPE_DEV = "stripe-integration-dev"
    _AMBERFLO_PROD = "amberflo-api-key-prod"
    _AMBERFLO_DEV = "amberflo-api-key-dev"

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._generators: dict[str, ValueGenerator] = {
            "django-secret-key": self._generate_django_secret_key,
            "posthog-django-secret-key": self._generate_django_secret_key,
            "github-app-creds": self._get_github_app_creds,
            "bitbucket-app-creds": self._get_bitbucket_app_creds,
            "bitbucket-oauth-creds": self._get_bitbucket_oauth_creds,
            "github-app-webhook-secrets": self._get_github_app_webhook_secrets,
            "toolshed-admin-github-oauth-app": self._get_toolshed_admin_github_secret,
            "github-app-private-key": self._get_github_app_private_key,
            "toolshed-cookie-salt": self._generate_secret_key,
            "duo-toolshed-app": self._get_duo_toolshed_secrets,
            "source-maps-private-key": self._get_source_maps_private_key,
            "bugout-api-key": self._get_butout_api_key,
            "stripe-integration": self._get_stripe_integration_secrets,
            "amberflo-api-key": self._get_amberflo_api_key,  # For remote cache (proxy/storage)
            "amberflo-integration": self._get_amberflo_api_key,  # For payments service (rotatable secret)
            "sendgrid-webhook": self._get_sendgrid_webhook_key,
        }
        self._simple_secrets = frozenset(("posthog-django-secret-key", "amberflo-api-key"))

        # Check that the secret names are valid if specified.
        if cmd_args.secrets:
            secret_names = set(cmd_args.secrets)
            invalid_secret_names = {name for name in secret_names if name not in self._generators}
            if invalid_secret_names:
                raise ToolchainAssertion(f"Invalid secret names: {', '.join(invalid_secret_names)}")
            self._secrets = secret_names
        else:
            self._secrets = set(self._generators.keys())
        self._overwrite = cmd_args.overwrite
        self._aws_region = cmd_args.aws_region
        self._dry_run = cmd_args.dry_run

        if cmd_args.local and cmd_args.namespaces:
            raise ToolchainAssertion("Can't specify both --local and --namespaces")
        if cmd_args.local and cmd_args.cluster is not None:
            raise ToolchainAssertion("Can't specify both --local and --cluster")
        if not cmd_args.local and cmd_args.cluster is None:
            raise ToolchainAssertion("Must specify one of --local or --cluster")

        self._cluster: KubernetesCluster | None = None
        if cmd_args.cluster is not None:
            self._cluster = KubernetesCluster(cmd_args.cluster)
        self._is_local = cmd_args.local
        self._is_prod = self._cluster in (KubernetesCluster.PROD, KubernetesCluster.REMOTING)
        if self._is_prod and cmd_args.namespaces:
            raise ToolchainAssertion(f"Not allowed to specify namespace for prod cluster: {self.cluster.value}")

        if self._cluster is not None:
            if self._is_prod:
                self._namespaces = get_namespaces_for_prod_cluster(self._cluster)
            else:  # dev cluster
                self._namespaces = tuple(cmd_args.namespaces) if cmd_args.namespaces else (get_remote_username(),)
        else:
            self._namespaces = tuple()

        if self._is_prod:
            self._bitbucket_creds = self._BITBUCKET_PROD
            self._github_app_creds = self._GITHUB_APP_CREDS_PROD
            self._duo_web_app = self._DUO_WEB_APP_PROD
            self._stripe = self._STRIPE_PROD
            self._amberflo = self._AMBERFLO_PROD
        else:
            self._bitbucket_creds = self._BITBUCKET_DEV
            self._github_app_creds = self._GITHUB_APP_CREDS_DEV
            self._duo_web_app = self._DUO_WEB_APP_DEV
            self._stripe = self._STRIPE_DEV
            self._amberflo = self._AMBERFLO_DEV
        self._secrets_helper = (
            SecretsAccessHelper.for_local()
            if self._is_local
            else SecretsAccessHelper.for_k8s_namespaces(cluster=self.cluster, namespaces=self._namespaces)
        )

    @property
    def cluster(self) -> KubernetesCluster:
        if self._cluster is not None:
            return self._cluster
        raise ToolchainAssertion("self.cluster accessed when in local mode")

    def run(self) -> int:
        if self._is_local:
            logger.info("Ensuring local secrets")
            self._ensure_secrets()
            return 0
        namespaces_str = ", ".join(self._namespaces)
        logger.info(f"Ensuring secrets in Kubernetes {self.cluster.value} namespaces: {namespaces_str}")
        self._ensure_secrets()
        return 0

    def _ensure_secrets(self) -> None:
        for secret_name in self._secrets:
            self._ensure_secret(secret_name)

    def _get_secret_value(self, secret_name: str, value_generator: ValueGenerator, rotatable: bool) -> str:
        can_update = "current_secret" in inspect.getfullargspec(value_generator).args
        result = self._secrets_helper.get_value_and_accessor(secret_name, rotatable=rotatable)
        if not result:
            logger.info(f"Creating secret {secret_name}.")
            return value_generator()
        secret_value, accessor = result
        if can_update:
            logging.info(f"Using/updating secret {secret_name} from {accessor}.")
            return value_generator(secret_value)  # type: ignore

        logging.info(f"Using secret {secret_name} from {accessor}.")
        return secret_value

    def _ensure_secret(
        self,
        secret_name: str,
    ):
        value_generator = self._generators[secret_name]
        is_rotatable = secret_name not in self._simple_secrets
        if not self._overwrite:
            secret_value = self._get_secret_value(secret_name, value_generator, rotatable=is_rotatable)
        else:
            secret_value = value_generator()
        self._secrets_helper.set_secret(secret_name, secret_value, self._dry_run, rotatable=is_rotatable)

    def _generate_secret_key(self) -> str:
        return get_random_string(1024)

    def _generate_django_secret_key(self) -> str:
        return json.dumps({"SECRET_KEY": get_random_string(50)})

    @property
    def _aws_secrets(self) -> AWSSecretsAccessor:
        return AWSSecretsAccessor(self._aws_region)

    def _get_github_app_private_key(self) -> str:
        return self._get_private_key_from_aws(self._github_app_creds, "GITHUB_APP_PRIVATE_KEY")

    def _get_source_maps_private_key(self) -> str:
        return self._get_private_key_from_aws("source_maps_keys", "js_sourcemap_private_key")

    def _get_private_key_from_aws(self, secret_name: str, key: str) -> str:
        app_secret = self._aws_secrets.get_json_secret_or_raise(secret_name)
        # Since it is multiline string, it is stored b64 encoded in AWS Secrets Manager.
        pk_b64 = app_secret[key].encode()
        return base64.b64decode(pk_b64).decode()

    def _get_github_app_webhook_secrets(self, current_secret: str | None = None) -> str:
        webhook_secrets = json.loads(current_secret) if current_secret else []
        app_secret = self._aws_secrets.get_json_secret_or_raise(self._github_app_creds)
        current_webhook_secret = app_secret["GITHUB_APP_WEBHOOK_SECRET"]
        webhook_secrets.append(current_webhook_secret)
        return json.dumps(webhook_secrets)

    def _get_toolshed_admin_github_secret(self) -> str:
        secret_name = "github-admin-oauth-app-creds-prod" if self._is_prod else "github-admin-oauth-app-creds-dev"
        toolshed_github_secret = self._aws_secrets.get_json_secret_or_raise(secret_name)
        return json.dumps(toolshed_github_secret)

    def _get_github_app_creds(self) -> str:
        # The source of truth of github app creds is github.com. However we can't easily get them from there
        # programmatically.  So we keep the raw (non-rotatable) secret value in AWS SecretsManager, as a convenience
        # for this script. The raw value on  AWS SecretsManager is not otherwise accessed directly by any code.
        creds = json.loads(self._aws_secrets.get_secret_or_raise(self._github_app_creds))
        # Convert GitHub app style creds (GITHUB_APP_CLIENT_ID/GITHUB_APP_CLIENT_SECRET)
        # to what our users/ui service currently expects the secrets to look like (oauth app creds)
        # We include both for now so we can transition to the new format
        return json.dumps(
            {
                "GITHUB_KEY": creds["GITHUB_APP_CLIENT_ID"],
                "GITHUB_SECRET": creds["GITHUB_APP_CLIENT_SECRET"],
                "GITHUB_APP_CLIENT_ID": creds["GITHUB_APP_CLIENT_ID"],
                "GITHUB_APP_CLIENT_SECRET": creds["GITHUB_APP_CLIENT_SECRET"],
            }
        )

    def _get_bitbucket_app_creds(self) -> str:
        app_secret = json.loads(self._aws_secrets.get_secret_or_raise(self._bitbucket_creds))
        return json.dumps(
            {
                "APP_CLIENT_ID": app_secret["APP_CLIENT_ID"],
                "APP_SECRET": app_secret["APP_SECRET"],
            }
        )

    def _get_bitbucket_oauth_creds(self) -> str:
        app_secret = json.loads(self._aws_secrets.get_secret_or_raise(self._bitbucket_creds))
        return json.dumps(
            {
                "BITBUCKET_OAUTH_CLIENT_KEY": app_secret["OAUTH_CLIENT_KEY"],
                "BITBUCKET_OAUTH_CLIENT_SECRET": app_secret["OAUTH_CLIENT_SECRET"],
            }
        )

    def _get_duo_toolshed_secrets(self) -> str:
        duo_toolshed_dict = self._aws_secrets.get_json_secret_or_raise(self._duo_web_app)
        cfg = DuoAuthConfig(
            secret_key=duo_toolshed_dict["CLIENT_SECRET"],
            application_key=duo_toolshed_dict["CLIENT_ID"],
            host=duo_toolshed_dict["HOST"],
        )
        return json.dumps(cfg.to_dict())

    def _get_butout_api_key(self) -> str:
        # Same secret for prod and dev
        bugout_api_key_dict = self._aws_secrets.get_json_secret_or_raise("bugout-api")
        return json.dumps(bugout_api_key_dict)

    def _get_stripe_integration_secrets(self) -> str:
        stripe_secrets_dict = self._aws_secrets.get_json_secret_or_raise(self._stripe)
        return json.dumps(stripe_secrets_dict)

    def _get_amberflo_api_key(self) -> str:
        secret = self._aws_secrets.get_secret_or_raise(self._amberflo)
        return secret

    def _get_sendgrid_webhook_key(self) -> str:
        return self._aws_secrets.get_secret_or_raise("sendgrid-webhook")

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        cls.add_aws_region_argument(parser)
        parser.add_argument("--dry-run", action="store_true", required=False, default=False, help="Dry run")
        parser.add_argument(
            "--overwrite",
            action="store_true",
            required=False,
            default=False,
            help="Overwrite secrets (regenerate or re-read from source)",
        )
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--local", action="store_true", default=False, help="Ensure secrets on local machine")
        group.add_argument("--cluster", action="store", default=None, help="Cluster into which to ensure secrets")
        parser.add_argument(
            "--namespaces",
            metavar="name",
            nargs="+",
            required=False,
            help="Ensure secrets in this kubernetes namespaces ",
        )
        parser.add_argument(
            "--secret",
            metavar="SECRET_NAME",
            dest="secrets",
            type=str,
            action="append",
            default=[],
            help="Restrict operation to the specified SECRET_NAME (may be specified multiple times)",
        )


if __name__ == "__main__":
    EnsureSecrets.start()
