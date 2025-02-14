# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest
from rest_framework.test import APIClient

from toolchain.django.site.models import Customer, Repo, ToolchainUser
from toolchain.django.site.test_helpers.models_helpers import create_staff


@pytest.mark.django_db()
@pytest.mark.urls("toolchain.service.users.api.urls")
class TestDependentResourcesCheckz:
    @pytest.fixture()
    def customer(self) -> Customer:
        return Customer.create(slug="acmeid", name="acme")

    @pytest.fixture()
    def repo(self, customer: Customer) -> Repo:
        return Repo.create("acmebotid", customer=customer, name="acmebot")

    @pytest.fixture()
    def user(self, customer: Customer) -> ToolchainUser:
        user = create_staff(username="kramer")
        customer.add_user(user)
        return user

    @pytest.fixture()
    def client(self) -> APIClient:
        return APIClient()

    def test_dependent_resources_check_view(
        self, client: APIClient, user: ToolchainUser, customer: Customer, repo: Repo
    ) -> None:
        response = client.get("/checksz/resourcez")
        assert response.status_code == 200
        assert response.json() == {"Customer": customer.pk, "Repo": repo.pk, "ToolchainUser": user.pk}
