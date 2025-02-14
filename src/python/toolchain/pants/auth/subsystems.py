# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from enum import Enum, unique

from pants.engine.goal import GoalSubsystem
from pants.option.option_types import BoolOption, DictOption, EnumOption, IntOption, StrListOption, StrOption
from pants.option.subsystem import Subsystem

from toolchain.pants.auth.client import ACQUIRE_TOKEN_GOAL_NAME
from toolchain.pants.auth.server import TestPage

DEFAULT_AUTH_FILE = ".pants.d/toolchain_auth/auth_token.json"


@unique
class OutputType(Enum):
    FILE = "file"
    CONSOLE = "console"


class AccessTokenAcquisitionGoalOptions(GoalSubsystem):
    name = ACQUIRE_TOKEN_GOAL_NAME
    help = "Acquire access tokens for the Toolchain service."

    local_port = IntOption("--local-port", default=None, help="Local web server port")
    output = EnumOption(  # type: ignore[call-overload]
        "--output",
        enum_type=OutputType,
        default=OutputType.FILE,
        help="Output method for the access token. Outputting to the console is useful if the token needs to be "
        "provided to CI.",
    )
    headless = BoolOption("--headless", default=False, help="Don't open a browser when acquiring the access token")
    test_page = EnumOption(  # type: ignore[call-overload]
        "--test-page",
        enum_type=TestPage,
        default=TestPage.NA,
        advanced=True,
        help="Helper to test success and error pages without triggering the auth flow.",
    )
    description = StrOption("--description", default=None, help="Token description")
    for_ci = BoolOption(
        "--for-ci",
        default=False,
        help=f"Generate a token with impersonation permissions that can be used in CI. Limited to org owners/admins. "
        f"Implies `--{ACQUIRE_TOKEN_GOAL_NAME}-output={OutputType.CONSOLE.value}`.",
    )
    remote_execution = BoolOption(
        "--remote-execution",
        default=False,
        advanced=True,
        help="[Limited Beta] Asks for a token with remote execution permissions. This will only work for Toolchain customers that have this feature enabled.",
    )


class AuthStoreOptions(Subsystem):
    options_scope = "auth"
    help = "Set up for authenticating with Toolchain."

    auth_file = StrOption(
        "--auth-file",
        default=DEFAULT_AUTH_FILE,
        help="Path (relative to the repo root) at which to store and read the auth token.",
    )
    from_env_var = StrOption(
        "--from-env-var", default=None, help="Load the access token from this environment variable"
    )
    ci_env_variables = StrListOption(
        "--ci-env-variables",
        help="Environment variables in CI used to identify the build (used for restricted tokens)",
    )
    org = StrOption("--org", default=None, help="Organization slug for public repo PRs.")
    restricted_token_matches = DictOption[str](
        "--restricted-token-matches",
        default={},
        advanced=True,
        help="A mapping of environment variable name to a regex that must match that variable's value "
        "in order for the plugin to request a restricted access token.",
    )

    token_expiration_threshold = IntOption(
        "--token-expiration-threshold",
        default=30,
        advanced=True,
        help="Threshold (in minutes) for token TTL before plugin asks for a new token.",
    )
