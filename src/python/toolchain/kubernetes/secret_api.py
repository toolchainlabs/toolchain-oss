# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import base64
import re
from typing import Optional

import kubernetes

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.kubernetes.kubernetes_api import KubernetesAPI


class SecretAPI(KubernetesAPI):
    def get_secret(self, secret_name: str) -> Optional[dict]:
        """Return secret value as a dict."""
        try:
            res = self.api.read_namespaced_secret(secret_name, self._namespace)
            value_dict = {key: base64.b64decode(val) for key, val in res.data.items()}
            return value_dict
        except self.ApiException as e:
            if e.status == 404:
                return None
            raise

    def set_secret(
        self,
        secret_name: str,
        value_dict: dict,
        create_if_nonexistent: bool = True,
        labels: Optional[dict[str, str]] = None,
    ) -> None:
        """Sets the secret value as a dict.

        Keys in the dict must be alphanumeric characters, '-', '_' or '.'. Values in the dict must be bytes. We
        base64-encode them, as required by Kubernetes Secret.
        """
        self.validate_secret_name(secret_name)

        data = {}
        for key, val in value_dict.items():
            self.validate_key(key)
            data[key] = base64.b64encode(val.encode() if isinstance(val, str) else val).decode("ascii")
            md = kubernetes.client.V1ObjectMeta(name=secret_name, labels=labels)
        secret_resource = kubernetes.client.V1Secret(metadata=md, data=data)
        try:
            self.api.replace_namespaced_secret(secret_name, self._namespace, secret_resource)
        except self.ApiException as e:
            if e.status == 404 and create_if_nonexistent:
                self.api.create_namespaced_secret(self._namespace, secret_resource)
            else:
                raise

    def delete_secret(self, secret_name: str):
        self.api.delete_namespaced_secret(secret_name, self._namespace)

    # A Secret name must be a valid subdomain. See
    # https://github.com/kubernetes/apimachinery/blob/kubernetes-1.14.0/pkg/util/validation/validation.go#L131
    _secret_name_re = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$")

    @classmethod
    def validate_secret_name(cls, secret_name: str):
        if cls._secret_name_re.match(secret_name) is None:
            raise ToolchainAssertion(
                f"Kubernetes Secret name must consist of lower case alphanumeric chars, '-' or '.', "
                f"and must start and end with an alphanumeric character : {secret_name}"
            )

    _key_re = re.compile(r"^[\w.-]+$")

    @classmethod
    def validate_key(cls, key):
        if cls._key_re.match(key) is None:
            raise ToolchainAssertion(
                f"Key in Kubernetes Secret must consist of alphanumeric chars, '-', '_' or '.' : {key}"
            )
