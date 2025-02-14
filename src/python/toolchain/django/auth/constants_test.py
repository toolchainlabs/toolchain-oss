# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.auth.constants import AccessTokenAudience


class TestAccessTokenAudience:
    def test_from_api_names(self) -> None:
        audience = AccessTokenAudience.from_api_names(["buildsense"])
        assert AccessTokenAudience.BUILDSENSE_API in audience
        assert AccessTokenAudience.DEPENDENCY_API not in audience
        assert AccessTokenAudience.IMPERSONATE not in audience

        audience = AccessTokenAudience.from_api_names(["buildsense", "dependency"])
        assert AccessTokenAudience.BUILDSENSE_API in audience
        assert AccessTokenAudience.DEPENDENCY_API in audience
        assert AccessTokenAudience.IMPERSONATE not in audience

        audience = AccessTokenAudience.from_api_names(["impersonate", "dependency"])
        assert AccessTokenAudience.BUILDSENSE_API not in audience
        assert AccessTokenAudience.DEPENDENCY_API in audience
        assert AccessTokenAudience.IMPERSONATE in audience

        audience = AccessTokenAudience.from_api_names(["impersonate", "exec", "buildsense", "cache_rw"])
        assert AccessTokenAudience.BUILDSENSE_API in audience
        assert AccessTokenAudience.DEPENDENCY_API not in audience
        assert AccessTokenAudience.CACHE_RO not in audience
        assert AccessTokenAudience.CACHE_RW in audience
        assert AccessTokenAudience.REMOTE_EXECUTION in audience

        with pytest.raises(ToolchainAssertion, match="Empty api names list."):
            AccessTokenAudience.from_api_names([])

    def test_has_all_audiences_empty(self) -> None:
        audience = AccessTokenAudience.DEPENDENCY_API
        with pytest.raises(ToolchainAssertion, match="No audiences specified."):
            audience.has_all_audiences()

    def test_has_all_audiences_single(self) -> None:
        audience = AccessTokenAudience.DEPENDENCY_API
        assert audience.has_all_audiences(AccessTokenAudience.IMPERSONATE, AccessTokenAudience.DEPENDENCY_API) is False
        assert audience.has_all_audiences(AccessTokenAudience.DEPENDENCY_API) is True
        assert audience.has_all_audiences(AccessTokenAudience.IMPERSONATE) is False
        assert (
            audience.has_all_audiences(AccessTokenAudience.BUILDSENSE_API, AccessTokenAudience.DEPENDENCY_API) is False
        )
        assert audience.has_all_audiences(AccessTokenAudience.BUILDSENSE_API) is False

    def test_has_all_audiences_multiple(self) -> None:
        audience = AccessTokenAudience.IMPERSONATE | AccessTokenAudience.DEPENDENCY_API
        assert audience.has_all_audiences(AccessTokenAudience.IMPERSONATE, AccessTokenAudience.DEPENDENCY_API) is True
        assert audience.has_all_audiences(AccessTokenAudience.DEPENDENCY_API) is True
        assert audience.has_all_audiences(AccessTokenAudience.IMPERSONATE) is True
        assert (
            audience.has_all_audiences(AccessTokenAudience.BUILDSENSE_API, AccessTokenAudience.DEPENDENCY_API) is False
        )
        assert audience.has_all_audiences(AccessTokenAudience.BUILDSENSE_API) is False

    @pytest.mark.parametrize(
        ("audience", "claim"),
        [
            (AccessTokenAudience.IMPERSONATE | AccessTokenAudience.BUILDSENSE_API, ["buildsense", "impersonate"]),
            (AccessTokenAudience.BUILDSENSE_API, ["buildsense"]),
            (AccessTokenAudience.DEPENDENCY_API, ["dependency"]),
            (
                AccessTokenAudience.IMPERSONATE
                | AccessTokenAudience.BUILDSENSE_API
                | AccessTokenAudience.DEPENDENCY_API,
                ["buildsense", "dependency", "impersonate"],
            ),
            (AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.REMOTE_EXECUTION, ["buildsense", "exec"]),
        ],
    )
    def test_to_claim(self, audience, claim):
        assert audience.to_claim() == claim

    def test_invalid_combination(self) -> None:
        with pytest.raises(
            ToolchainAssertion, match="Token is not allowed to have both internal and impersonate permissions"
        ):
            AccessTokenAudience.for_pants_client(with_impersonation=True, internal_toolchain=True)

    def test_merge(self) -> None:
        assert (
            AccessTokenAudience.merge(
                allowed=AccessTokenAudience.FRONTEND_API,
                requested=AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.FRONTEND_API,
            )
            == AccessTokenAudience.FRONTEND_API
        )

        assert (
            AccessTokenAudience.merge(
                allowed=AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.FRONTEND_API,
                requested=AccessTokenAudience.FRONTEND_API,
            )
            == AccessTokenAudience.FRONTEND_API
        )
        assert (
            AccessTokenAudience.merge(
                allowed=AccessTokenAudience.FRONTEND_API,
                requested=AccessTokenAudience.BUILDSENSE_API,
            )
            is None
        )

    def test_merge_read_only_user(self) -> None:
        assert (
            AccessTokenAudience.merge(
                allowed=AccessTokenAudience.FRONTEND_API,
                requested=AccessTokenAudience.for_pants_client(),
            )
            is None
        )

        assert (
            AccessTokenAudience.merge(
                allowed=AccessTokenAudience.FRONTEND_API,
                requested=AccessTokenAudience.FRONTEND_API,
            )
            == AccessTokenAudience.FRONTEND_API
        )

    def test_merge_write_only_user(self) -> None:
        assert (
            AccessTokenAudience.merge(
                allowed=AccessTokenAudience.BUILDSENSE_API,
                requested=AccessTokenAudience.FRONTEND_API,
            )
            is None
        )

        assert (
            AccessTokenAudience.merge(
                allowed=AccessTokenAudience.BUILDSENSE_API,
                requested=AccessTokenAudience.for_pants_client(),
            )
            == AccessTokenAudience.BUILDSENSE_API
        )

    def test_has_caching(self) -> None:
        audience = AccessTokenAudience.IMPERSONATE | AccessTokenAudience.DEPENDENCY_API
        assert audience.has_caching is False
        audience = AccessTokenAudience.IMPERSONATE | AccessTokenAudience.CACHE_RO | AccessTokenAudience.BUILDSENSE_API
        assert audience.has_caching is True

        audience = AccessTokenAudience.IMPERSONATE | AccessTokenAudience.CACHE_RW | AccessTokenAudience.BUILDSENSE_API
        assert audience.has_caching is True

        audience = AccessTokenAudience.IMPERSONATE | AccessTokenAudience.CACHE_RW | AccessTokenAudience.CACHE_RO
        assert audience.has_caching is True

        audience = AccessTokenAudience.IMPERSONATE | AccessTokenAudience.BUILDSENSE_API
        assert audience.has_caching is False

        audience = AccessTokenAudience.BUILDSENSE_API
        assert audience.has_caching is False

    def test_to_dispaly(self) -> None:
        assert (AccessTokenAudience.IMPERSONATE | AccessTokenAudience.CACHE_RO).to_display() == "CACHE_RO, IMPERSONATE"
        assert (AccessTokenAudience.CACHE_RO | AccessTokenAudience.IMPERSONATE).to_display() == "CACHE_RO, IMPERSONATE"
        assert AccessTokenAudience.CACHE_RW.to_display() == "CACHE_RW"
        assert AccessTokenAudience.BUILDSENSE_API.to_display() == "BUILDSENSE_API"
        assert (
            AccessTokenAudience.CACHE_RO | AccessTokenAudience.REMOTE_EXECUTION | AccessTokenAudience.IMPERSONATE
        ).to_display() == "CACHE_RO, IMPERSONATE, REMOTE_EXECUTION"
        audience = AccessTokenAudience.INTERNAL_TOOLCHAIN
        audience &= ~AccessTokenAudience.INTERNAL_TOOLCHAIN
        assert audience.to_display() == "N/A"

    def test_api_name(self) -> None:
        assert AccessTokenAudience.CACHE_RW.api_name == "cache_rw"
        assert AccessTokenAudience.BUILDSENSE_API.api_name == "buildsense"
        assert AccessTokenAudience.REMOTE_EXECUTION.api_name == "exec"
        audience = AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.CACHE_RW
        with pytest.raises(ToolchainAssertion, match="Multiple flags are enabled"):
            audience.api_name  # pylint: disable=pointless-statement
