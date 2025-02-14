# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from collections.abc import Iterator
from enum import Enum, Flag, auto, unique
from functools import reduce
from operator import ior, or_

from toolchain.base.toolchain_error import ToolchainAssertion

_logger = logging.getLogger(__name__)


REFRESH_TOKEN_COOKIE_NAME = "refreshToken"


@unique
class AccessTokenType(Enum):
    REFRESH_TOKEN = "refresh"
    ACCESS_TOKEN = "access"


class AccessTokenAudience(Flag):
    BUILDSENSE_API = auto()
    DEPENDENCY_API = auto()
    CACHE_RW = auto()
    CACHE_RO = auto()
    FRONTEND_API = auto()  # Associated with APIs serving the JS SPA.
    # Allows user impersonation, useful when running in CI and we want the operation to count against the user that created the PR/commit and not
    # against the user who created the token
    IMPERSONATE = auto()
    # Certain views can allow internal users to use certain flows that external users are not allowed to use.
    INTERNAL_TOOLCHAIN = auto()
    REMOTE_EXECUTION = auto()

    @classmethod
    def for_pants_client(
        cls,
        with_impersonation: bool = False,
        internal_toolchain: bool = False,
        with_remote_execution: bool = False,
    ) -> AccessTokenAudience:
        if with_impersonation and internal_toolchain:
            raise ToolchainAssertion("Token is not allowed to have both internal and impersonate permissions.")
        audience = cls.BUILDSENSE_API | cls.CACHE_RO | cls.CACHE_RW
        if with_impersonation:
            audience |= cls.IMPERSONATE
        if internal_toolchain:
            audience |= cls.INTERNAL_TOOLCHAIN
        if with_remote_execution:
            audience |= cls.REMOTE_EXECUTION
        return audience

    @classmethod
    def from_api_names(cls, api_names: list[str]) -> AccessTokenAudience:
        if not api_names:
            raise ToolchainAssertion("Empty api names list.")
        api_names_map = {aud.api_name: aud for aud in cls}
        return reduce(ior, (api_names_map[name] for name in api_names))

    @classmethod
    def merge(cls, *, allowed: AccessTokenAudience, requested: AccessTokenAudience) -> AccessTokenAudience | None:
        merged = [aud for aud in cls if aud in allowed and aud in requested]
        return reduce(or_, merged) if merged else None

    @property
    def can_impersonate(self) -> bool:
        return self.has_all_audiences(self.IMPERSONATE)  # type: ignore[arg-type]

    def _check_audiences(self, audiences: tuple[AccessTokenAudience, ...]) -> Iterator[bool]:
        if not audiences:
            raise ToolchainAssertion("No audiences specified.")
        for audience in audiences:
            yield audience in self

    def has_all_audiences(self, *audiences: AccessTokenAudience) -> bool:
        return all(self._check_audiences(audiences))

    @property
    def current_values(self) -> tuple[AccessTokenAudience, ...]:
        if self.name is None:
            # self.name is None when multiple values are set
            return tuple(aud for aud in AccessTokenAudience if aud in self)
        return (self,)

    def to_claim(self) -> list[str]:
        return sorted(aud.api_name for aud in self.current_values)

    @property
    def has_caching(self) -> bool:
        return any(self._check_audiences((self.CACHE_RW, self.CACHE_RO)))  # type: ignore[arg-type]

    @property
    def has_remote_execution(self) -> bool:
        return self.has_all_audiences(self.REMOTE_EXECUTION)  # type: ignore[arg-type]

    @property
    def has_frontend_api(self) -> bool:
        return self.has_all_audiences(self.FRONTEND_API)  # type: ignore[arg-type]

    @property
    def api_name(self) -> str:
        if self in _API_NAMES_OVERRIDE_MAP:
            return _API_NAMES_OVERRIDE_MAP[self]
        return self._get_name().lower().replace("_api", "")

    def _get_name(self) -> str:
        if not self.name:
            raise ToolchainAssertion("Multiple flags are enabled.")
        return self.name

    def to_display(self) -> str:
        if not self:
            return "N/A"
        return ", ".join(sorted(aud._get_name() for aud in self.current_values))


_API_NAMES_OVERRIDE_MAP = {AccessTokenAudience.REMOTE_EXECUTION: "exec"}
