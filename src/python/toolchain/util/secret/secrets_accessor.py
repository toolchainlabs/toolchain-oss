# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path

from toolchain.aws.secretsmanager import SecretsManager
from toolchain.base.fileutil import safe_mkdir
from toolchain.base.toolchain_error import ToolchainError
from toolchain.kubernetes.constants import KubernetesCluster
from toolchain.kubernetes.secret_api import SecretAPI
from toolchain.util.secret.rotatable_secret import RotatableSecret

_logger = logging.getLogger(__name__)


class SecretNotFound(ToolchainError):
    def __init__(self, secret_name: str, error_note: str):
        super().__init__(f"Secret '{secret_name}' not found. {error_note}")


class SecretsReader:
    """Base class for classes that get raw secret strings."""

    @property
    def error_note(self) -> str:
        note = getattr(self, "ERROR_NOTE", "")
        return f"{note} {self}"

    def get_secret_or_raise(self, secret_name: str) -> str:
        """Gets the secret value as a character string.

        :raises SecretNotFound: if no secret of the given name found.
        """
        ret = self.get_secret(secret_name)
        if ret is None:
            raise SecretNotFound(secret_name, self.error_note)
        return ret

    def get_json_secret_or_raise(self, secret_name: str) -> dict:
        ret = self.get_json_secret(secret_name)
        if ret is None:
            raise SecretNotFound(secret_name, self.error_note)
        return ret

    def get_json_secret(self, secret_name: str) -> dict | None:
        ret = self.get_secret(secret_name)
        if ret is None:
            return None
        # When using rotatable secrets the returned secrets might already be json.
        # Need to debug more. This is a short term fix.
        return ret if isinstance(ret, dict) else json.loads(ret)

    def get_secret(self, secret_name: str) -> str | None:
        """Gets the secret value as a character string.

        Returns None if no such secret exists.
        """
        raise NotImplementedError()

    def get_secret_and_version(self, secret_name: str) -> tuple[str | None, str | None]:
        val = self.get_secret(secret_name)
        version = hashlib.sha256(val.encode("utf8")).hexdigest() if val else None
        return val, version

    def get_version(self, secret_name: str) -> str | None:
        _, version = self.get_secret_and_version(secret_name)
        return version


class SecretsAccessor(SecretsReader):
    """Base class for classes that get and set raw secret strings."""

    def set_secret(self, secret_name, value):
        """Sets the secret value as a character string.

        Creates the secret if it doesn't already exist.
        """
        raise NotImplementedError()


class RotatableSecretsAccessor(SecretsAccessor):
    """An accessor for RotatableSecrets.

    Wraps secret values in RotatableSecret and access them through an underlying SecretsAccessor.
    """

    def __init__(self, accessor, compressed=False):
        self._accessor = accessor
        self._compressed = compressed

    @property
    def error_note(self) -> str:
        return self._accessor.error_note

    def get_rotatable_secret(self, secret_name):
        return RotatableSecret(self._accessor, secret_name, compressed=self._compressed)

    def get_secret(self, secret_name):
        return self.get_rotatable_secret(secret_name).get_current_value()

    def set_secret(self, secret_name, value):
        rs = self.get_rotatable_secret(secret_name)
        rs.propose_value(value)
        rs.promote_proposed_value_to_current()

    def __repr__(self):
        return f"RotatableSecretsAccessor[{self._accessor!r}]"


class DummySecretsAccessor(SecretsAccessor):
    """A dummy secrets accessor for use in tests.

    Also implemented as a singleton so we can share the same secrets when accessing using different code paths.
    """

    _instance = None

    @classmethod
    def get_instance(cls):
        if not cls._instance:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def create_rotatable(cls):
        return RotatableSecretsAccessor(cls.get_instance())

    def __init__(self):
        self.secrets = {}

    def get_secret(self, secret_name):
        return self.secrets.get(secret_name)

    def set_secret(self, secret_name, value):
        self.secrets[secret_name] = value


class LocalSecretsAccessor(SecretsAccessor):
    """A SecretsAccessor that uses local files.

    Useful for local development. NOT SECURE FOR PRODUCTION USE!
    """

    ERROR_NOTE = "Make sure you created secrets. See https://github.com/toolchainlabs/toolchain/tree/master/src/python/toolchain/prod/#ensure_secretspy"

    @classmethod
    def create_rotatable(
        cls, secrets_dir: str | None = None, for_k8s_volume_reader: bool = False
    ) -> RotatableSecretsAccessor:
        return RotatableSecretsAccessor(cls(secrets_dir=secrets_dir, for_k8s_volume_reader=for_k8s_volume_reader))

    def __init__(self, secrets_dir: str | None = None, for_k8s_volume_reader: bool = False) -> None:
        self._for_k8s_volume_reader = for_k8s_volume_reader
        self._secrets_dir = Path(secrets_dir) if secrets_dir else Path.home() / ".toolchain_secrets_dev"
        safe_mkdir(self._secrets_dir.as_posix())

    def get_secret(self, secret_name: str) -> str | None:
        secret_path = self._secret_path(secret_name)
        if not secret_path.exists():
            return None
        return secret_path.read_text(encoding="utf-8")

    def set_secret(self, secret_name: str, value: str) -> None:
        secret_path = self._secret_path(secret_name)
        secret_path.parent.mkdir(parents=True, exist_ok=True)
        with open(os.open(secret_path.as_posix(), os.O_WRONLY | os.O_CREAT, 0o600), "wb") as fp:
            fp.write(value.encode("utf8"))
        _logger.info(f"saved secret={secret_name} to {secret_path.as_posix()}")

    def _secret_path(self, secret_name: str) -> Path:
        path = self._secrets_dir / secret_name
        if self._for_k8s_volume_reader:
            path = path / KubernetesSecretsAccessor.secret_string_key
        return path

    def __str__(self) -> str:
        return f"LocalSecretsAccessor(dir={self._secrets_dir})"

    def __repr__(self) -> str:
        return str(self)


class AWSSecretsAccessor(SecretsAccessor):
    """A SecretsAccessor that accesses the AWS SecretsManager."""

    def __init__(self, region: str) -> None:
        self._aws_secretsmanager = SecretsManager(region=region)

    def get_secret(self, secret_name: str) -> str | None:
        return self._aws_secretsmanager.get_secret(secret_name)

    def set_secret(self, secret_name: str, value: str) -> None:
        self._aws_secretsmanager.set_secret(secret_name, value, create_if_nonexistent=True)
        _logger.info(f"saved secret={secret_name} to AWS secrets namanger")


class KubernetesSecretsAccessor(SecretsAccessor):
    """A SecretsAccessor that accesses Kubernetes Secret resources.

    Useful for setup scripts and code with access to the Kubernetes API. Running pods should normally use
    KubernetesVolumeSecretsReader instead.
    """

    # By convention, we put the secret string at this key in the Kubernetes Secret's data dict.
    secret_string_key = "secret_string"
    ERROR_NOTE = "Make sure you created secrets. See https://github.com/toolchainlabs/toolchain/tree/master/src/python/toolchain/prod/#ensure_secretspy"

    @classmethod
    def create_rotatable(cls, namespace, cluster: KubernetesCluster | None = None) -> RotatableSecretsAccessor:
        return RotatableSecretsAccessor(cls.create(namespace, cluster))

    @classmethod
    def create(cls, namespace: str, cluster: KubernetesCluster | None = None) -> KubernetesSecretsAccessor:
        if cluster:
            api = SecretAPI.for_cluster(cluster=cluster, namespace=namespace)
        else:
            api = SecretAPI.for_pod(namespace)
        return cls(api)

    def __init__(self, api) -> None:
        self._kubernetes_secret_api = api

    def get_secret(self, secret_name: str) -> str | None:
        value_dict = self._kubernetes_secret_api.get_secret(secret_name)
        if value_dict is None:
            return None
        return value_dict[self.secret_string_key].decode("utf8")

    def set_secret(self, secret_name: str, value: str | dict[str, str | bytes]) -> None:
        value_dict = {self.secret_string_key: value.encode()} if isinstance(value, str) else value
        self._kubernetes_secret_api.set_secret(secret_name, value_dict, labels={"services": "toolchain"})
        _logger.info(f"saved secret={secret_name} to a kubernetes namespace={self._kubernetes_secret_api.namespace}")

    def __repr__(self):
        ns = self._kubernetes_secret_api.namespace
        return f"KubernetesSecretsAccessor(namespace={ns})"


class KubernetesVolumeSecretsReader(SecretsReader):
    """A SecretsReader that reads secrets mounted into volumes.

    This is how Kubernetes makes secrets available to pods at runtime.
    """

    @classmethod
    def create_rotatable(
        cls, base_path: str | None = None, secrets_path: str | None = None
    ) -> RotatableSecretsAccessor:
        return RotatableSecretsAccessor(cls(base_path=base_path, secrets_path=secrets_path))

    def __init__(self, base_path: str | None = None, secrets_path: str | None = None) -> None:
        self._base_path = self.get_secrets_path(base_path, secrets_path)

    @classmethod
    def get_secrets_path(cls, base_path: str | None, secrets_path: str | None = None) -> Path:
        return Path(base_path) if base_path else Path(os.sep) / (secrets_path or "secrets")

    def get_secret(self, secret_name: str) -> str | None:
        key = KubernetesSecretsAccessor.secret_string_key
        secret_path = self._base_path / secret_name / key
        if not secret_path.exists():
            _logger.warning(f"Secret not found under {secret_path}")
            return None
        return secret_path.read_text("utf-8")

    def __repr__(self):
        return f"KubernetesVolumeSecretsReader(base_path={self._base_path})"


class ChainedSecretsReader(SecretsReader):
    """A SecretsReader that delegates to a list of underlying readers.

    Returns the value in the first reader in the list that has the secret. Returns None if no reader in the list has the
    secret.
    """

    def __init__(self, *readers: SecretsReader) -> None:
        self._readers = readers

    def get_secret(self, secret_name: str) -> str | None:
        for reader in self._readers:
            val = reader.get_secret(secret_name)
            if val is not None:
                return val
        return None


class TrackingSecretsReader(SecretsReader):
    """A SecretsReader that keeps track of which secrets have been read."""

    _names_and_versions: dict[str, str | None] = {}

    @classmethod
    def clear(cls) -> None:
        """For use under tests to ensure we don't mess state."""
        cls._names_and_versions = {}

    def __init__(self, reader: SecretsReader) -> None:
        self._reader = reader

    @classmethod
    def _track(cls, secret_name: str, version: str | None) -> None:
        cls._names_and_versions[secret_name] = version

    @classmethod
    def get_tracked_secrets(cls) -> dict[str, str | None]:
        return dict(cls._names_and_versions)  # Defensive copy

    def get_secret(self, secret_name: str) -> str | None:
        value, version = self._reader.get_secret_and_version(secret_name)
        self._track(secret_name, version)
        return value

    def __repr__(self) -> str:
        return f"TrackingSecretsReader[{self._reader!r}]"
