# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from toolchain.util.elasticsearch.config import ElasticSearchConfig


class BuildSenseElasticSearchConfig(ElasticSearchConfig):
    HOST_CONFIG_FIELD = "BUILDSENSE_ELASTICSEARCH_HOST"

    def __init__(
        self,
        host: str,
        port: int,
        is_local_proxy: bool,
        connection_cls=None,
        max_retries: int = 3,
        indices_names: tuple[str, ...] = tuple(),
    ) -> None:
        super().__init__(
            host=host, port=port, is_local_proxy=is_local_proxy, connection_cls=connection_cls, max_retries=max_retries
        )
        self._indices_names = indices_names or ("buildsense-v2",)

    @property
    def doc_type(self) -> str:
        return "run_info"

    @property
    def indices_names(self) -> tuple[str, ...]:
        return self._indices_names

    @property
    def existing_index(self) -> str:
        return self.indices_names[0]

    @property
    def new_index(self) -> str | None:
        names = self.indices_names
        return names[-1] if len(names) > 1 else None

    @property
    def alias_name(self) -> str:
        return "buildsense"
