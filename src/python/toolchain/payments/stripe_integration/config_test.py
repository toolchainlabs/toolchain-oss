# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.constants import ToolchainEnv
from toolchain.payments.stripe_integration.config import StripeConfiguration
from toolchain.payments.stripe_integration.test_utils.utils import add_product_and_prices_search_responses
from toolchain.util.config.app_config import AppConfig


class TestStripeConfiguration:
    @pytest.mark.parametrize("tc_env", [ToolchainEnv.DEV, ToolchainEnv.PROD])  # type: ignore[attr-defined]
    def test_minimal_config(self, tc_env: ToolchainEnv) -> None:
        app_cfg = AppConfig({"STRIPE_CONFIG": {"default_price_id": "newman"}})
        string_cfg = StripeConfiguration.from_config(app_cfg, tc_env)
        assert string_cfg.trial_price_id == "newman"
        assert string_cfg.trial_period_days == 30

    @pytest.mark.parametrize("tc_env", [ToolchainEnv.DEV, ToolchainEnv.PROD])  # type: ignore[attr-defined]
    def test_config(self, tc_env: ToolchainEnv) -> None:
        app_cfg = AppConfig({"STRIPE_CONFIG": {"default_price_id": "david-puddy", "trial_period_days": 41}})
        string_cfg = StripeConfiguration.from_config(app_cfg, tc_env)
        assert string_cfg.trial_price_id == "david-puddy"
        assert string_cfg.trial_period_days == 41

    def test_missing_prod_config(self) -> None:
        app_cfg = AppConfig({})
        with pytest.raises(ToolchainAssertion, match="Invalid/Missing stripe config"):
            StripeConfiguration.from_config(app_cfg, ToolchainEnv.PROD)  # type: ignore[attr-defined]

    def test_invalid_prod_config(self) -> None:
        app_cfg = AppConfig({"STRIPE_CONFIG": {"trial_period_days": 41}})
        with pytest.raises(ToolchainAssertion, match="Invalid/Missing stripe config"):
            StripeConfiguration.from_config(app_cfg, ToolchainEnv.PROD)  # type: ignore[attr-defined]

    def test_dev_get_price_from_api(self, responses) -> None:
        app_cfg = AppConfig({})
        add_product_and_prices_search_responses(responses)
        string_cfg = StripeConfiguration.from_config(app_cfg, ToolchainEnv.DEV)  # type: ignore[attr-defined]
        assert string_cfg.trial_price_id == "price_no_bagel_no_bagel_no_bagel"
        assert string_cfg.trial_period_days == 30
