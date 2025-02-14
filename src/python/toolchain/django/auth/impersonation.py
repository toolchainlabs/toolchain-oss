# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass

from toolchain.django.site.models import ToolchainUser

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImpersonationData:
    user: ToolchainUser
    impersonator: ToolchainUser
    expiry: datetime.datetime

    def to_json_dict(self) -> dict[str, str]:
        return {
            "user_username": self.user.username,
            "user_full_name": self.user.full_name,
            "user_api_id": self.user.api_id,
            "impersonator_username": self.impersonator.username,
            "impersonator_full_name": self.impersonator.full_name,
            "impersonator_api_id": self.impersonator.api_id,
            "expiry": self.expiry.isoformat(),
        }
