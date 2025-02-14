# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
from dataclasses import dataclass


@dataclass(frozen=True)
class JWTConfig:
    default_token_ttl: datetime.timedelta
    token_with_caching_ttl: datetime.timedelta
    token_with_remote_exec_ttl: datetime.timedelta

    @classmethod
    def for_dev(cls) -> JWTConfig:
        return cls(
            default_token_ttl=datetime.timedelta(minutes=10),
            token_with_caching_ttl=datetime.timedelta(minutes=45),
            token_with_remote_exec_ttl=datetime.timedelta(hours=4),
        )

    @classmethod
    def for_prod(cls) -> JWTConfig:
        # for now, will follow up with logic to read from config.
        return cls.for_dev()
