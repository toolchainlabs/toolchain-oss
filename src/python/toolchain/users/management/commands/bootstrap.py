# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.auth.constants import AccessTokenAudience
from toolchain.django.site.models import Customer, Repo, ToolchainUser
from toolchain.users.models import AuthProvider, OptionalBool, UserAuth, UserCustomerAccessConfig


def _get_str(prompt) -> str:
    value = ""
    while not value:
        value = input(f"{prompt}: ").strip()
    return value


class Command(BaseCommand):
    help = "Boostrap toolchain data in Dev DB."

    def _get_github_user_details(self) -> dict:
        user_handle = _get_str("Enter github handle")
        response = requests.get(f"https://api.github.com/users/{user_handle}")
        response.raise_for_status()
        return response.json()

    def handle(self, *args, **options):
        if not settings.TOOLCHAIN_ENV.is_dev:
            raise ToolchainAssertion("This is for dev only!")
        username = _get_str(
            "Enter toolchain username (from your @toolchain.com email address, but just the username part not the full email address)"
        )
        gh_user = self._get_github_user_details()
        # Slugs must match the fake github org we use in dev, specified in pants.localdev.toml
        customer = Customer.for_slug(slug="seinfeld") or Customer.create(
            slug="seinfeld", name="Toolchain [DEV]", customer_type=Customer.Type.INTERNAL
        )
        if Repo.get_or_none(slug="toolchain"):
            return
        Repo.create(slug="toolchain", customer=customer, name="Toolchain Repo [DEV]")
        self.stdout.write(self.style.SUCCESS("Toolchain customer & repo created"))
        avatar_url = gh_user["avatar_url"]
        user = ToolchainUser.create(username=username, email=f"{username}@toolchain.com")
        user_id = str(gh_user["id"])
        github_username = gh_user["login"]
        UserAuth.update_or_create(
            user=user, provider=AuthProvider.GITHUB, user_id=user_id, username=github_username, emails=[]
        )
        user.avatar_url = avatar_url
        user.is_staff = True
        user.save()
        UserCustomerAccessConfig.create_readwrite(
            customer_id=customer.id, user_api_id=user.api_id, is_org_admin=OptionalBool.TRUE
        )
        uac = UserCustomerAccessConfig.objects.get(customer_id=customer.id, user_api_id=user.api_id)
        uac.set_allowed_audiences(uac.allowed_audiences | AccessTokenAudience.REMOTE_EXECUTION)
