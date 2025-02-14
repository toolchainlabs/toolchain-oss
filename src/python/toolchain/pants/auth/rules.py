# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# This pylint ignore is due to the migration of the pants options API, when we remove backward compatibility we should also remove this line
# pylint: disable=unexpected-keyword-arg

from __future__ import annotations

import logging
import os
import socket
import time
import uuid
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Type, TypeVar
from urllib.parse import urlencode

import requests
from pants.engine.console import Console
from pants.engine.fs import CreateDigest, Digest, FileContent, Workspace
from pants.engine.goal import Goal, GoalSubsystem
from pants.engine.rules import Get, collect_rules, goal_rule, rule
from pants.option.global_options import GlobalOptions
from pants.option.option_types import BoolOption, IntOption

# Renamed in 2.15.x.
try:
    from pants.engine.env_vars import EnvironmentVars, EnvironmentVarsRequest
except ImportError:
    from pants.engine.environment import Environment as EnvironmentVars  # type: ignore
    from pants.engine.environment import EnvironmentRequest as EnvironmentVarsRequest  # type: ignore

from toolchain.base.datetime_tools import utcnow
from toolchain.pants.auth.client import ACQUIRE_TOKEN_GOAL_NAME, AuthClient, AuthError
from toolchain.pants.auth.server import AuthFlowHttpServer, TestPage
from toolchain.pants.auth.store import AuthStore
from toolchain.pants.auth.subsystems import AccessTokenAcquisitionGoalOptions, AuthStoreOptions, OutputType
from toolchain.pants.auth.token import AuthToken
from toolchain.pants.common.network import get_common_request_headers
from toolchain.pants.common.toolchain_setup import ToolchainSetup
from toolchain.util.constants import REQUEST_ID_HEADER

_logger = logging.getLogger(__name__)


def optional_file_option(fn: str) -> str:
    # Similar to Pant's file_option, but doesn't require the file to exist.
    return os.path.normpath(fn)


_Goal = TypeVar("_Goal", bound="Goal")


def _mark_environment_behavior(cls: Type[_Goal]) -> Type[_Goal]:
    """Conditionally mark a `Goal` subclass as being migrated to the new environments behavior.

    This decorator exists for backwards compatibility with Pants pre-2.15. Once support for 2.14 ends, remove this
    decorator, and move the `environment_behavior` settings directly to the `Goal` subclasses we are decorating.
    """
    EnvironmentBehavior = getattr(Goal, "EnvironmentBehavior", None)
    if EnvironmentBehavior is not None:
        cls.environment_behavior = getattr(EnvironmentBehavior, "LOCAL_ONLY", None)  # type: ignore
    return cls


class AuthTokenInfoGoalOptions(GoalSubsystem):
    name = "auth-token-info"
    help = "Show information about the current auth token used to access the Toolchain service"
    verbose = BoolOption("--verbose", default=False, help="Show all JWT claims for the current auth token")
    json = BoolOption("--json", default=False, help="Show JWT claims in JSON format (implies `verbose`).")


@_mark_environment_behavior
class AuthTokenInfo(Goal):
    subsystem_cls = AuthTokenInfoGoalOptions


class AuthTokenCheckGoalOptions(GoalSubsystem):
    name = "auth-token-check"
    help = "Check if the Toolchain auth token has expired or if it is about to expire"
    threshold = IntOption(
        "--threshold", default=14, help="Threshold in days to fail the check before the token expiration"
    )


@_mark_environment_behavior
class AuthTokenCheck(Goal):
    subsystem_cls = AuthTokenCheckGoalOptions


@_mark_environment_behavior
class AccessTokenAcquisition(Goal):
    subsystem_cls = AccessTokenAcquisitionGoalOptions


@dataclass(frozen=True)
class AccessTokenAcquisitionOptions:
    output: OutputType
    auth_options: AuthClient
    repo_name: str
    org_name: str | None
    local_port: int | None
    headless: bool
    test_page: TestPage
    description: str
    ask_for_impersonation: bool
    ask_for_remote_execution: bool

    @classmethod
    def from_options(
        cls,
        *,
        acquire_options: AccessTokenAcquisitionGoalOptions,
        store_options: AuthStoreOptions,
        pants_bin_name: str,
        repo_name: str,
        org_name: str | None,
        base_url: str,
    ) -> AccessTokenAcquisitionOptions:
        auth_opts = AuthClient.create(
            pants_bin_name=pants_bin_name,
            base_url=f"{base_url}/api/v1",
            auth_file=store_options.auth_file,
            context="auth-acquire",
        )
        return cls(
            local_port=acquire_options.local_port,
            repo_name=repo_name,
            org_name=org_name,
            auth_options=auth_opts,
            output=acquire_options.output,
            headless=acquire_options.headless,
            test_page=acquire_options.test_page,
            description=acquire_options.description or "N/A",
            ask_for_impersonation=acquire_options.for_ci,
            ask_for_remote_execution=acquire_options.remote_execution,
        )

    @property
    def log_only(self) -> bool:
        return self.output == OutputType.CONSOLE or self.ask_for_impersonation

    @property
    def base_url(self) -> str:
        return self.auth_options.base_url

    def get_auth_url(self, *, org: str | None, repo: str, params: dict[str, str]) -> str:
        params["repo"] = f"{org}/{repo}" if org else repo
        encoded_params = urlencode(params)
        return f"{self.base_url}/token/auth/?{encoded_params}"

    def get_token_exchange_url(self) -> str:
        return f"{self.base_url}/token/exchange/"

    @property
    def auth_file_path(self) -> Path:
        return self.auth_options.auth_file_path


@rule
async def construct_auth_store(
    auth_store_config: AuthStoreOptions,
    global_options: GlobalOptions,
    toolchain_setup: ToolchainSetup,
) -> AuthStore:
    environment = await Get(EnvironmentVars, EnvironmentVarsRequest(AuthStore.relevant_env_vars(auth_store_config)))
    return AuthStore(
        context="rule-construct-auth-store",
        options=auth_store_config,
        pants_bin_name=global_options.options.pants_bin_name,
        env=dict(environment),
        repo=toolchain_setup.safe_get_repo_name(),
        base_url=toolchain_setup.base_url,
    )


@goal_rule(desc="Acquires access token from Toolchain Web App and store it locally")
async def acquire_access_token(
    console: Console,
    workspace: Workspace,
    acquire_goal_options: AccessTokenAcquisitionGoalOptions,
    store_options: AuthStoreOptions,
    global_options: GlobalOptions,
    toolchain_setup: ToolchainSetup,
) -> AccessTokenAcquisition:
    repo_name = toolchain_setup.get_repo_name()
    acquire_options = AccessTokenAcquisitionOptions.from_options(
        pants_bin_name=global_options.options.pants_bin_name,
        acquire_options=acquire_goal_options,
        store_options=store_options,
        repo_name=repo_name,
        org_name=toolchain_setup.org_name,
        base_url=toolchain_setup.base_url,
    )
    if acquire_options.test_page != TestPage.NA:
        _test_local_server(acquire_options)
        return AccessTokenAcquisition(exit_code=0)
    try:
        auth_token = _acquire_token(console, acquire_options)
    except AuthError as error:
        console.print_stderr(str(error))
        return AccessTokenAcquisition(exit_code=-1)
    if acquire_options.log_only:
        console.print_stdout(f"Access Token is: {auth_token.access_token}")
        return AccessTokenAcquisition(exit_code=0)
    # stores token locally
    auth_file_path = acquire_options.auth_file_path
    digest = await Get(
        Digest, CreateDigest([FileContent(path=auth_file_path.name, content=auth_token.to_json_string().encode())])
    )
    workspace.write_digest(digest=digest, path_prefix=str(auth_file_path.parent))
    console.print_stdout("Access token acquired and stored.")
    return AccessTokenAcquisition(exit_code=0)


@goal_rule(desc=AuthTokenInfoGoalOptions.help)
async def show_token_info(
    console: Console,
    auth_store: AuthStore,
    options: AuthTokenInfoGoalOptions,
) -> AuthTokenInfo:
    for line in auth_store.get_token_info(verbose=options.verbose, use_json=options.json):
        console.print_stdout(line)
    return AuthTokenInfo(exit_code=0)


@goal_rule(desc=AuthTokenCheckGoalOptions.help)
async def check_auth_token(
    console: Console,
    auth_store: AuthStore,
    options: AuthTokenCheckGoalOptions,
) -> AuthTokenCheck:
    refresh_token = auth_store.load_refresh_token()
    if not refresh_token:
        console.print_stderr("Token not found")
        return AuthTokenCheck(exit_code=-1)
    time_until_expiration = refresh_token.expires_at - utcnow()
    if time_until_expiration.total_seconds() < 0:
        console.print_stderr(f"Token expired at {refresh_token.expires_at.isoformat()}")
        return AuthTokenCheck(exit_code=-1)
    if time_until_expiration.days <= options.threshold:
        console.print_stderr(
            f"Token will expire in {time_until_expiration.days} days at {refresh_token.expires_at.isoformat()}"
        )
        return AuthTokenCheck(exit_code=-1)
    console.print_stdout(
        f"Token will expire in {time_until_expiration.days} days at {refresh_token.expires_at.isoformat()}"
    )
    return AuthTokenCheck(exit_code=0)


def _acquire_token(console: Console, options: AccessTokenAcquisitionOptions) -> AuthToken:
    if options.headless or not _is_browser_available():
        return _acquire_token_headless(console, options)
    return _acquire_token_with_browser(console, options)


def _test_local_server(options: AccessTokenAcquisitionOptions):
    with AuthFlowHttpServer.create_server(port=options.local_port, expected_state=str(uuid.uuid4())) as http_server:
        http_server.start_thread()
        server_url = http_server.get_test_url(options.test_page)
        success = webbrowser.open(server_url, new=1, autoraise=True)
        if not success:
            http_server.shutdown()
            raise AuthError(
                f"Failed to open web browser. {ACQUIRE_TOKEN_GOAL_NAME} can't continue.", context="auth-acquire"
            )
        time.sleep(4)  # sleep to allow the browser to load the page from the server.


def _acquire_token_with_browser(console: Console, options: AccessTokenAcquisitionOptions) -> AuthToken:
    state = str(uuid.uuid4())
    with AuthFlowHttpServer.create_server(port=options.local_port, expected_state=state) as http_server:
        http_server.start_thread()
        callback_url = http_server.server_url
        console.print_stdout(f"Local Web Server running - callback at: {callback_url}")
        params = {"redirect_uri": callback_url, "state": state}
        auth_url = options.get_auth_url(org=options.org_name, repo=options.repo_name, params=params)
        _logger.debug(f"Open Browser at: {auth_url}")
        success = webbrowser.open(auth_url, new=1, autoraise=True)
        if not success:
            http_server.shutdown()
            raise AuthError(
                f"Failed to open web browser. {ACQUIRE_TOKEN_GOAL_NAME} can't continue.", context="auth-acquire"
            )
        token_code = http_server.wait_for_code()
        desc = _get_token_desc(options)
        return _exchage_code_for_token(console, options, token_code, description=desc)


def _exchage_code_for_token(
    console: Console, options: AccessTokenAcquisitionOptions, token_code: str, description: str
) -> AuthToken:
    # TODO: Use an engine intrinsic instead of directly going to the network.
    headers = get_common_request_headers()
    data = {"code": token_code, "desc": description}
    if options.ask_for_impersonation:
        data["allow_impersonation"] = "1"
    if options.ask_for_remote_execution:
        data["remote_execution"] = "1"
    with requests.post(options.get_token_exchange_url(), data=data, headers=headers) as response:
        if not response.ok:
            console.print_stderr(console.red(_get_error_message(response)))
            raise AuthError("Failed to acquire access token from server", context="auth-acquire")
        resp_data = response.json()
        return AuthToken.from_json_dict(resp_data)


def _acquire_token_headless(console: Console, options: AccessTokenAcquisitionOptions) -> AuthToken:
    url = options.get_auth_url(org=options.org_name, repo=options.repo_name, params={"headless": "1"})
    console.print_stdout(f"Using a web browser navigate to: {url}")
    # TODO: use console to get input from the user. https://github.com/pantsbuild/pants/issues/11398
    token_code = input("Type or paste in the token exchange code: ")
    desc = _get_token_desc(options)
    return _exchage_code_for_token(console, options, token_code, description=desc)


def _is_browser_available() -> bool:
    try:
        webbrowser.get()
    except webbrowser.Error:
        return False
    return True


def _get_error_message(response) -> str:
    error_message = None
    request_id = response.headers.get(REQUEST_ID_HEADER, "NA")
    if response.headers.get("Content-Type") == "application/json":
        error_message = response.json().get("message")

    if not error_message:
        error_message = f"Unknown error: {response.text}"
    return f"HTTP: {response.status_code}: {error_message} request={request_id}"


def get_auth_rules():
    return collect_rules()


def _get_token_desc(options: AccessTokenAcquisitionOptions) -> str:
    if options.description:
        return options.description
    default_desc = socket.gethostname()
    if options.log_only:
        default_desc += " [for CI]"
    # TODO: use console to get input from the user. https://github.com/pantsbuild/pants/issues/11398
    user_desc = input(f"Enter token description [{default_desc}]: ")
    return user_desc or default_desc
