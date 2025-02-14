# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

import stripe

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.constants import ToolchainEnv

_logger = logging.getLogger(__name__)


def init_stripe(*, tc_env: ToolchainEnv, secrets_reader) -> None:
    api_key = secrets_reader.get_json_secret_or_raise("stripe-integration")["api-key"]
    is_test_mode_key = "_test_" in api_key
    _logger.info(f"init stripe. {is_test_mode_key=}")
    if tc_env.is_dev and not is_test_mode_key:  # type: ignore[attr-defined]
        raise ToolchainAssertion("non dev API key used in dev env!")
    if tc_env.is_prod and is_test_mode_key:  # type: ignore[attr-defined]
        raise ToolchainAssertion("Dev mode API key used in production")
    stripe.api_key = api_key
