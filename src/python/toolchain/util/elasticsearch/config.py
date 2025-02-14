# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from toolchain.base.toolchain_error import ToolchainAssertion


class ElasticSearchConfig:
    HOST_CONFIG_FIELD = "ELASTICSEARCH_HOST"

    @classmethod
    def for_lambda(cls, es_host: str):
        return cls(host=es_host, port=443, is_local_proxy=False)

    @classmethod
    def for_env(cls, *, toolchain_env, is_k8s, config):
        if not toolchain_env.is_prod_or_dev:
            raise ToolchainAssertion("Only prod & dev environments are supported.")
        if not is_k8s:
            return cls(host="localhost", port=9200, is_local_proxy=True)
        host = config.get(cls.HOST_CONFIG_FIELD)
        return cls(host=host, port=443, is_local_proxy=False)

    @classmethod
    def for_tests(cls, connection_cls, max_retries: int = 0, **kwargs):
        if not connection_cls:
            raise ToolchainAssertion("Must provide a connection_cls for test, try DummyElasticRequests")
        return cls(
            host="ovaltine.search.local",
            port=77,
            is_local_proxy=True,
            connection_cls=connection_cls,
            max_retries=max_retries,
            # Subclasses may have extra kwargs params for __init__method
            **kwargs,  # type: ignore[call-arg]
        )

    def __init__(
        self, *, host: str, port: int, is_local_proxy: bool, connection_cls: type | None = None, max_retries: int = 3
    ) -> None:
        if not host:
            raise ToolchainAssertion("ES Host not configured.")
        self._is_local_proxy = is_local_proxy
        self._host = host
        self._port = port
        self._connection_cls = connection_cls
        self._max_retries = max_retries

    @property
    def connection_cls(self):
        return self._connection_cls

    @property
    def host(self):
        return self._host

    def get_es_hosts(self):
        return [{"host": self._host, "port": self._port}]

    @property
    def needs_auth(self):
        return not self._is_local_proxy

    @property
    def max_retries(self) -> int:
        return self._max_retries

    def __str__(self):
        return f"{type(self).__name__} host={self.host}:{self._port} connection_cls={self.connection_cls}"

    def __repr__(self):
        return str(self)
