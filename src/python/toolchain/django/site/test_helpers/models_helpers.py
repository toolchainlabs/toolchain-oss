# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

from toolchain.base.datetime_tools import utcnow
from toolchain.django.auth.constants import AccessTokenAudience
from toolchain.django.site.models import AllocatedRefreshToken, Customer, ToolchainUser
from toolchain.users.models import AuthProvider, UserAuth


def create_customer(slug: str) -> Customer:
    customer = Customer.create(slug, f"org-{slug}")
    return customer


def create_github_user(
    username: str,
    email: str | None = None,
    full_name: str | None = None,
    github_user_id: str | None = None,
    github_username: str | None = None,
) -> ToolchainUser:
    email = email or f"{username}@jerrysplace.com"
    github_user_id = github_user_id or "837432"
    github_username = github_username or f"gh-{username}"
    user = ToolchainUser.create(
        username=username, email=email, full_name=full_name, avatar_url=f"https://pictures.jerry.com/{github_username}"
    )
    UserAuth.update_or_create(
        user=user, provider=AuthProvider.GITHUB, user_id=github_user_id, username=github_username, emails=[email]
    )
    assert user.last_login is None
    return user


def create_bitbucket_user(
    username: str,
    bitbucket_user_id: str,
    email: str | None = None,
    full_name: str | None = None,
    bitbucket_username: str | None = None,
) -> ToolchainUser:
    email = email or f"{username}@nyc.com"
    bitbucket_username = bitbucket_username or f"bitbucket-{username}"
    user = ToolchainUser.create(
        username=username,
        email=email,
        full_name=full_name,
        avatar_url=f"https://pictures.mandelbaum.com/{bitbucket_username}",
    )
    UserAuth.update_or_create(
        user=user,
        provider=AuthProvider.BITBUCKET,
        user_id=bitbucket_user_id,
        username=bitbucket_username,
        emails=[email],
    )
    assert user.last_login is None
    return user


def create_staff(
    username: str,
    email: str | None = None,
    github_user_id: str | None = None,
    github_username: str | None = None,
    full_name: str | None = None,
) -> ToolchainUser:
    # User must have GH data in order to be a staff user.
    user = create_github_user(
        username=username,
        email=email,
        full_name=full_name,
        github_user_id=github_user_id,
        github_username=github_username,
    )
    user.is_staff = True
    user.save()
    assert user.last_login is None
    return user


def allocate_fake_api_tokens(user: ToolchainUser, count: int, base_time: datetime.datetime | None = None) -> list[str]:
    base_time = base_time or utcnow()
    expiration = base_time + datetime.timedelta(days=10)
    return [
        AllocatedRefreshToken.allocate_api_token(
            user_api_id=user.api_id,
            issued_at=base_time,
            expires_at=expiration,
            description=f"festivus-{i}",
            repo_id="tinsel",
            audience=AccessTokenAudience.BUILDSENSE_API
            | AccessTokenAudience.IMPERSONATE
            | AccessTokenAudience.CACHE_RW,
        )
        for i in range(count)
    ]
