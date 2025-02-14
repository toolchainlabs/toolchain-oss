# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from dataclasses import dataclass

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.constants import ToolchainEnv
from toolchain.payments.stripe_integration.stripe_client import get_default_stripe_product
from toolchain.util.config.app_config import AppConfig

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StripeConfiguration:
    trial_price_id: str
    trial_period_days: int

    @classmethod
    def from_config(cls, config: AppConfig, toolchain_env: ToolchainEnv) -> StripeConfiguration:
        stripe_cfg = config.get_config_section("STRIPE_CONFIG")
        price_id = stripe_cfg.get("default_price_id")
        # To make things easier in dev, we allow getting the price ID dynamically in dev, but in prod it must be provided via config.
        if not price_id:
            if not toolchain_env.is_dev:  # type: ignore[attr-defined]
                raise ToolchainAssertion("Invalid/Missing stripe config")
            _logger.info("get default price ID via the stripe API")
            price_id = get_default_stripe_product().price_id

        return cls(
            trial_price_id=price_id,
            trial_period_days=stripe_cfg.get("trial_period_days", 30),
        )
