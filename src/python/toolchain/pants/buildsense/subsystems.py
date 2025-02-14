# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# This pylint ignore is due to the migration of the pants options API, when we remove backward compatibility we should also remove this line
# pylint: disable=unexpected-keyword-arg
from __future__ import annotations

import logging
import os
import re
from typing import Mapping

from pants.option.option_types import BoolOption, IntOption, StrListOption, StrOption
from pants.option.subsystem import Subsystem

logger = logging.getLogger(__name__)


def optional_dir_option(dn: str) -> str:
    # Similar to Pant's dir_option, but doesn't require the directory to exist.
    return os.path.normpath(dn)


class CaptureCIEnv:
    _DEFAULT_CI_MAP = {
        "CIRCLECI": r"^CIRCLE.*",
        "GITHUB_ACTIONS": r"^GITHUB.*",
        # Unlike other CI systems, BITBUCKET doesn't have a default env variable that
        # indicates the it is a bitbucket environment.
        # See: https://support.atlassian.com/bitbucket-cloud/docs/variables-and-secrets/
        "BITBUCKET_BUILD_NUMBER": r"^BITBUCKET.*",
        "BUILDKITE": r"^BUILDKITE.*",
    }
    DEFAULT_EXCLUDE_TERMS = ("ACCESS", "TOKEN", "SECRET", "JWT")

    def __init__(self, *, pattern: str | None, exclude_terms: list[str], ci_map: dict[str, str] | None = None) -> None:
        self._pattern = re.compile(pattern) if pattern else None
        self._exclude_expression = re.compile("|".join(f".*{re.escape(v)}.*" for v in exclude_terms))
        self._ci_map = {ci: re.compile(pattern) for ci, pattern in (ci_map or self._DEFAULT_CI_MAP).items()}

    def _get_pattern(self, env: Mapping[str, str]) -> re.Pattern | None:
        for ci_name, capture_expression in self._ci_map.items():
            if ci_name in env:
                return capture_expression
        return None

    def capture(self, env: Mapping[str, str]) -> dict[str, str] | None:
        captured = self._capture_ci_env(env)
        return self._scrub(captured) if captured else None

    def _capture_ci_env(self, env: Mapping[str, str]) -> dict[str, str] | None:
        pattern = self._pattern or self._get_pattern(env)
        if not pattern:
            return None
        return {key: value for key, value in env.items() if pattern.match(key)}

    def _scrub(self, captured: dict[str, str]) -> dict[str, str]:
        scrubbed_keys = set()
        final_data = {}
        for key, value in captured.items():
            if self._exclude_expression.match(key):
                scrubbed_keys.add(key)
            else:
                final_data[key] = value
        captured_str = ",".join(sorted(captured.keys()))
        if scrubbed_keys:
            final_captured_str = ",".join(sorted(final_data.keys()))
            logger.debug(f"captured CI env: {captured_str} scrubbed: {scrubbed_keys} final: {final_captured_str}")
        else:
            logger.debug(f"captured CI env: {captured_str}")
        return final_data


class Reporter(Subsystem):
    options_scope = "buildsense"
    help = """Configuration for Toolchain's BuildSense reporting."""

    timeout = IntOption(
        "--timeout", advanced=True, default=10, help="Wait at most this many seconds for network calls to complete."
    )
    dry_run = BoolOption("--dry-run", advanced=True, default=False, help="Go thru the motions w/o making network calls")
    local_build_store = BoolOption(
        "--local-build-store", advanced=True, default=True, help="Store failed uploads and try to upload later."
    )
    local_store_base = StrOption(
        "--local-store-base",
        advanced=True,
        default=".pants.d/toolchain/buildsense/",
        help="Base directory for storing buildsense data locally.",
    )
    max_batch_size_mb = IntOption(
        "--max-batch-size-mb",
        advanced=True,
        default=20,
        help="Maximum batch size to try and upload (uncompressed).",
    )
    ci_env_var_pattern = StrOption(
        "--ci-env-var-pattern",
        advanced=True,
        default=None,
        help="CI Environment variables regex pattern.",
    )
    enable = BoolOption("--enable", default=True, help="Enables the BuildSense reporter plugin.")
    log_upload = BoolOption(
        "--log-upload",
        default=True,
        advanced=True,
        help="Upload pants logs to buildsense",
    )

    ci_env_scrub_terms = StrListOption(
        "--ci-env-scrub-terms",
        default=list(CaptureCIEnv.DEFAULT_EXCLUDE_TERMS),
        advanced=True,
        help="patterns for environment variables to exclude from uploaded CI env variables.",
    )

    show_link = BoolOption(
        "--show-link",
        default=True,
        advanced=True,
        help="Show link to the pants run in BuildSense Web UI.",
    )
    collect_platform_data = BoolOption(
        "--collect-platform-data",
        default=False,
        advanced=True,
        help="Should BuildSense collect and upload platform platform information (os version, platform architecture, python version, etc...).",
    )
    log_final_upload_latency = BoolOption(
        "--log-final-upload-latency",
        default=False,
        advanced=True,
        help="Should BuildSense log the time it took to upload data at the end of the run.",
    )
    batch_timeout = IntOption("--batch-timeout", advanced=True, default=40, help="Timeout for batch upload.")
