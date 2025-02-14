# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
from collections.abc import Sequence
from types import GeneratorType

import pytest
from django.db import IntegrityError
from django.http import Http404
from freezegun import freeze_time

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.auth.constants import AccessTokenAudience
from toolchain.django.site.models import (
    AccessTokenState,
    AccessTokenUsage,
    AllocatedRefreshToken,
    Customer,
    CustomerSaveError,
    CustomerScmProvider,
    CustomerUser,
    MaxActiveTokensReachedError,
    Repo,
    RepoCreationError,
    RepoState,
    ToolchainUser,
    transaction,
)
from toolchain.django.site.test_helpers.models_helpers import allocate_fake_api_tokens
from toolchain.util.test.util import assert_messages


@pytest.mark.django_db()
class TestUserModel:
    def test_with_api_error(self) -> None:
        with pytest.raises(ToolchainAssertion, match="user_api_ids is empty"):
            ToolchainUser.with_api_ids(user_api_ids=[])

    def test_get_by_api_id(self) -> None:
        u1 = ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")
        u2 = ToolchainUser.create(username="jerry", email="jerry@seinfeld.com", avatar_url="https://pole.com/festivus")
        assert ToolchainUser.get_by_api_id("newman") is None
        assert ToolchainUser.get_by_api_id(u1.api_id) == u1
        loaded_u2 = ToolchainUser.get_by_api_id(u2.api_id)
        assert loaded_u2 == u2
        assert loaded_u2.avatar_url == "https://pole.com/festivus"

        loaded_u2.deactivate()
        assert ToolchainUser.get_by_api_id(u2.api_id) is None

    def test_with_api_ids(self, django_assert_num_queries) -> None:
        u1 = ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")

        u2 = ToolchainUser.create(username="jerry", email="jerry@seinfeld.com")
        u3 = ToolchainUser.create(username="kramer", email="kramer@seinfeld.com")
        ToolchainUser.create(username="george", email="george@seinfeld.com")
        ToolchainUser.create(username="elaine", email="elaine@seinfeld.com")
        with django_assert_num_queries(1):
            users = list(ToolchainUser.with_api_ids([u1.api_id, u3.api_id, u2.api_id, "gold"]))
            assert set(users) == {u1, u3, u2}

    def test_deactivate(self) -> None:
        u1 = ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")
        u2 = ToolchainUser.create(username="jerry", email="jerry@seinfeld.com")
        users = list(ToolchainUser.with_api_ids({u1.api_id, u2.api_id, "gold"}))
        assert set(users) == {u1, u2}
        u2.deactivate()
        assert ToolchainUser.objects.get(id=u2.id).is_active is False
        users = list(ToolchainUser.with_api_ids([u1.api_id, u2.api_id, "gold"]))
        assert set(users) == {u1}
        users = list(ToolchainUser.with_api_ids((u1.api_id, u2.api_id, "gold"), include_inactive=True))
        assert set(users) == {u1, u2}
        assert ToolchainUser.get_by_api_id(u2.api_id) is None

    def test_with_user_names(self, django_assert_num_queries) -> None:
        u1 = ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")
        u2 = ToolchainUser.create(username="jerry", email="jerry@seinfeld.com")
        u3 = ToolchainUser.create(username="kramer", email="kramer@seinfeld.com")
        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer_2 = Customer.create(slug="usps", name="Postal Service")
        with django_assert_num_queries(1):
            assert ToolchainUser.with_user_names(customer_1.pk, {"kenny", "kramer", "jerry"}) == tuple()
        customer_1.add_user(u1)
        customer_1.add_user(u2)

        with django_assert_num_queries(1):
            assert ToolchainUser.with_user_names(customer_2.pk, {"kenny", "kramer", "jerry"}) == tuple()

        customer_2.add_user(u3)

        with django_assert_num_queries(1):
            assert set(ToolchainUser.with_user_names(customer_1.pk, {"kenny", "kramer", "jerry"})) == {u1, u2}

        with django_assert_num_queries(1):
            assert set(ToolchainUser.with_user_names(customer_1.pk, {"kenny", "kramer"})) == {u1}

        with django_assert_num_queries(1):
            assert ToolchainUser.with_user_names(customer_2.pk, {"kenny", "jerry"}) == tuple()

        with django_assert_num_queries(1):
            assert set(ToolchainUser.with_user_names(customer_2.pk, {"kramer", "jerry"})) == {u3}

    def test_is_same_customer_associated(self) -> None:
        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer_2 = Customer.create(slug="usps", name="Postal Service")
        user_1 = ToolchainUser.create(username="jerry", email="jerry@seinfeld.com")
        user_2 = ToolchainUser.create(username="cosmo", email="cosmo@seinfeld.com")

        # same user association
        assert user_1.is_same_customer_associated(user_1.api_id, "chicken") is True
        assert user_2.is_same_customer_associated(user_2.api_id, "tinsel") is True

        # Users w/o customers
        assert user_1.is_same_customer_associated(user_2.api_id, customer_1.pk) is False
        assert user_2.is_same_customer_associated(user_1.api_id, customer_1.pk) is False

        # Only 'admin' user is part of customer org
        customer_1.add_user(user_1)
        assert user_1.is_same_customer_associated(user_2.api_id, customer_1.pk) is False
        assert user_2.is_same_customer_associated(user_1.api_id, customer_1.pk) is False

        # Both users are part of org 1
        customer_1.add_user(user_2)
        assert user_1.is_same_customer_associated(user_2.api_id, customer_1.pk) is True
        assert user_2.is_same_customer_associated(user_1.api_id, customer_1.pk) is True

        # Both users are part of org 1, not org 2
        assert user_1.is_same_customer_associated(user_2.api_id, customer_2.pk) is False
        assert user_2.is_same_customer_associated(user_1.api_id, customer_2.pk) is False

        # Admin in org 1 cannot impersonate a user that is member of a different org (customer 2) if it not a member of that org.
        customer_2.add_user(user_2)
        assert user_1.is_same_customer_associated(user_2.api_id, customer_2.pk) is False
        assert user_2.is_same_customer_associated(user_1.api_id, customer_2.pk) is False

        # Inactive customers don't count.
        customer_1.deactivate()
        assert user_1.is_same_customer_associated(user_2.api_id, customer_1.pk) is False

    def test_get_inactive_users_api_ids(self) -> None:
        u1 = ToolchainUser.create(username="jerry", email="jerry@seinfeld.com")
        ToolchainUser.create(username="cosmo", email="cosmo@seinfeld.com")
        ToolchainUser.create(username="george", email="george@seinfeld.com")
        u4 = ToolchainUser.create(username="newman", email="newman@seinfeld.com")
        ToolchainUser.create(username="elaine", email="elaine@seinfeld.com")
        u6 = ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")
        ToolchainUser.create(username="joe", email="joe@seinfeld.com")
        assert isinstance(ToolchainUser.get_inactive_users_api_ids(), GeneratorType)
        assert next(ToolchainUser.get_inactive_users_api_ids(), None) is None
        u1.deactivate()
        assert {u1.api_id} == set(ToolchainUser.get_inactive_users_api_ids())
        u4.deactivate()
        u6.deactivate()
        assert {u1.api_id, u4.api_id, u6.api_id} == set(ToolchainUser.get_inactive_users_api_ids())

    def set_staff_status_no_no_user_details(self):
        user = ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")
        assert user.is_staff is False
        assert user.is_superuser is False
        # no user details, so this is_staff should be set to false on save.
        user.is_staff = True
        user.save()
        assert user.is_staff is False
        assert user.is_superuser is False
        user = ToolchainUser.objects.get(id=user.id)
        assert user.is_staff is False
        assert user.is_superuser is False

    def test_staff_status(self):
        user = ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")
        assert user.is_staff is False
        assert user.is_superuser is False
        user.is_staff = True
        assert user.is_superuser is False
        user.save()
        assert user.is_staff is True
        assert user.is_superuser is True
        user = ToolchainUser.objects.get(id=user.id)
        assert user.is_staff is True
        assert user.is_superuser is True

    def test_staff_status_on_deactivate(self):
        user = ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")
        user.is_staff = True
        user.save()
        user = ToolchainUser.objects.get(id=user.id)
        assert user.is_staff is True
        assert user.is_superuser is True
        user.is_active = False
        assert user.is_staff is True
        assert user.is_superuser is True
        user.save()
        assert user.is_active is False
        assert user.is_staff is False
        assert user.is_superuser is False
        user = ToolchainUser.objects.get(id=user.id)
        assert user.is_active is False
        assert user.is_staff is False
        assert user.is_superuser is False

    def test_create(self) -> None:
        user_1 = ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")
        assert user_1.is_active is True
        user_1.first_name = "Kenny"
        user_1.last_name = "Kramer"
        user_1.save()
        user_2 = ToolchainUser.create(username="jerry", email="jerry@seinfeld.com", full_name="Jerry Seinfeld")
        assert user_2.is_active is True
        user_2.first_name = "Hello"
        user_2.last_name = "Newman"
        loaded_user_1 = ToolchainUser.objects.get(api_id=user_1.api_id)
        loaded_user_2 = ToolchainUser.objects.get(api_id=user_2.api_id)
        assert loaded_user_1.is_active is True
        assert loaded_user_2.is_active is True
        assert loaded_user_1.full_name == ""
        assert loaded_user_1.get_full_name() == loaded_user_1.username == "kenny"
        assert user_1.email == loaded_user_1.email == "kenny@seinfeld.com"
        assert user_1.avatar_url == ""
        assert user_1.username == loaded_user_1.username == "kenny"
        assert user_1.full_name == loaded_user_1.full_name == ""
        assert user_2.email == loaded_user_2.email == "jerry@seinfeld.com"
        assert user_2.username == loaded_user_2.username == "jerry"
        assert user_2.full_name == loaded_user_2.full_name == "Jerry Seinfeld"
        assert user_2.avatar_url == ""
        assert loaded_user_2.get_full_name() == "Jerry Seinfeld"
        assert user_1 == loaded_user_1
        assert user_2 == loaded_user_2

    def test_create_inactive(self) -> None:
        user_1 = ToolchainUser.create(username="kenny", email="kenny@seinfeld.com", is_active=False)
        user_2 = ToolchainUser.create(
            username="jerry", email="jerry@seinfeld.com", full_name="Jerry Seinfeld", is_active=False
        )
        assert user_1.is_active is False
        assert user_2.is_active is False
        loaded_user_1 = ToolchainUser.objects.get(api_id=user_1.api_id)
        loaded_user_2 = ToolchainUser.objects.get(api_id=user_2.api_id)
        assert loaded_user_1.is_active is False
        assert loaded_user_2.is_active is False

    def _setup_users(self) -> None:
        ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")
        ToolchainUser.create(username="jerry", email="jerry@seinfeld.com", full_name="Jerry Seinfeld").deactivate()
        ToolchainUser.create(username="george", email="geroge@seinfeld.com")
        assert ToolchainUser.active_users().count() == 2
        assert ToolchainUser.objects.count() == 3

    def test_is_username_exists(self) -> None:
        self._setup_users()
        assert ToolchainUser.is_username_exists("kenny") is True
        assert ToolchainUser.is_username_exists("jerry") is True
        assert ToolchainUser.is_username_exists("george") is True
        assert ToolchainUser.is_username_exists("elaine") is False
        assert ToolchainUser.is_username_exists("George") is True
        assert ToolchainUser.is_username_exists("JERRY") is True

    def test_is_email_exists(self) -> None:
        self._setup_users()
        assert ToolchainUser.is_email_exists("kenny@seinfeld.com") is True
        assert ToolchainUser.is_email_exists("kenny@nyccom") is False
        assert ToolchainUser.is_email_exists("jerry@seinfeld.com") is True
        assert ToolchainUser.is_email_exists("jerry@sEinfeld.COM") is True
        assert ToolchainUser.is_email_exists("jerry@seinfeld.com".capitalize()) is True
        assert ToolchainUser.is_email_exists("jerry@seinfeld.com".upper()) is True
        assert ToolchainUser.is_email_exists("geroge+mail@seinfeld.com") is False
        assert ToolchainUser.is_email_exists("Geroge@seinfeld.com") is True

    def test_get_user_api_id_for_username(self, django_assert_num_queries) -> None:
        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer_2 = Customer.create(slug="usps", name="Postal Service")
        customer_3 = Customer.create(slug="nbc", name="NBC")
        u1 = ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")
        customer_1.add_user(u1)
        u2 = ToolchainUser.create(username="jerry", email="jerry@seinfeld.com", full_name="Jerry Seinfeld")
        customer_2.add_user(u2)
        u3 = ToolchainUser.create(username="george", email="geroge@seinfeld.com")
        customer_1.add_user(u3)
        customer_2.add_user(u3)
        ToolchainUser.create(username="cosmo", email="cosmo@seinfeld.com")
        with django_assert_num_queries(1):
            assert ToolchainUser.get_user_api_id_for_username("kenny", customer_1.id) == u1.api_id
        assert ToolchainUser.get_user_api_id_for_username("kenNY", customer_1) == u1.api_id
        assert ToolchainUser.get_user_api_id_for_username("kenNY", customer_2) is None
        assert ToolchainUser.get_user_api_id_for_username("ken", customer_1) is None
        assert ToolchainUser.get_user_api_id_for_username("george", customer_1) == u3.api_id
        assert ToolchainUser.get_user_api_id_for_username("george", customer_2) == u3.api_id
        assert ToolchainUser.get_user_api_id_for_username("george", customer_3) is None
        assert ToolchainUser.get_user_api_id_for_username("elaine", customer_2) is None
        assert ToolchainUser.get_user_api_id_for_username("George", customer_2) == u3.api_id
        assert ToolchainUser.get_user_api_id_for_username("cosmo", customer_1) is None
        assert ToolchainUser.get_user_api_id_for_username("cosmo", customer_2) is None
        # Active users only!
        assert ToolchainUser.get_user_api_id_for_username("JERRY", customer_2) == u2.api_id
        u2.deactivate()
        assert ToolchainUser.get_user_api_id_for_username("JERRY", customer_2) is None
        assert ToolchainUser.get_user_api_id_for_username("jerry", customer_2) is None

    def test_set_customers(self) -> None:
        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer_2 = Customer.create(slug="usps", name="Postal Service")
        customer_3 = Customer.create(
            slug="jpeterman", name="The J. Peterman Company", customer_type=Customer.Type.OPEN_SOURCE
        )
        assert customer_1.is_open_source is False
        assert customer_2.is_open_source is False
        assert customer_3.is_open_source is True
        user_1 = ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")
        user_2 = ToolchainUser.create(username="jerry", email="jerry@seinfeld.com", full_name="Jerry Seinfeld")
        assert CustomerUser.objects.count() == 0

        # Set empty on empty
        user_1.set_customers(set())
        assert CustomerUser.objects.count() == 0
        assert not user_1.customers_ids

        # Add to empty
        user_1.set_customers({customer_2.id, customer_3.id})
        assert CustomerUser.objects.count() == 2
        assert set(user_1.customers_ids) == {customer_2.id, customer_3.id}

        # remove & keep
        user_1.set_customers({customer_2.id, customer_1.id})
        assert CustomerUser.objects.count() == 2
        assert set(user_1.customers_ids) == {customer_2.id, customer_1.id}

        # Add to existing
        user_1.set_customers({customer_3.id, customer_2.id, customer_1.id})
        assert CustomerUser.objects.count() == 3
        assert set(user_1.customers_ids) == {customer_3.id, customer_2.id, customer_1.id}

        # Remove two customers
        user_1.set_customers({customer_1.id})
        assert CustomerUser.objects.count() == 1
        assert set(user_1.customers_ids) == {customer_1.id}

        # Add & remove
        user_1.set_customers({customer_3.id})
        assert CustomerUser.objects.count() == 1
        assert set(user_1.customers_ids) == {customer_3.id}

        # No-op
        user_1.set_customers({customer_3.id})
        assert CustomerUser.objects.count() == 1
        assert set(user_1.customers_ids) == {customer_3.id}

        # No cross user impact
        user_2.set_customers({customer_3.id, customer_2.id})
        assert CustomerUser.objects.count() == 3
        assert set(user_1.customers_ids) == {customer_3.id}
        assert set(user_2.customers_ids) == {customer_3.id, customer_2.id}

    def test_is_associated_with_active_customers(self) -> None:
        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer_2 = Customer.create(slug="usps", name="Postal Service")
        user = ToolchainUser.create(username="jerry", email="jerry@seinfeld.com", full_name="Jerry Seinfeld")
        assert user.is_associated_with_active_customers() is False
        customer_1.add_user(user)
        assert user.is_associated_with_active_customers() is True
        customer_2.add_user(user)
        assert user.is_associated_with_active_customers() is True
        customer_1.deactivate()
        assert user.is_associated_with_active_customers() is True
        customer_2.deactivate()
        assert user.is_associated_with_active_customers() is False


@pytest.mark.django_db()
class TestCustomerModel:
    @pytest.mark.parametrize(
        ("slug_1", "slug_2"),
        [
            ("jerry", "UsPS"),
            ("Jerry", "USPS"),
            ("JeRRY", "usps"),
            ("JERRY", "uSPS"),
        ],
    )
    def test_for_slugs(self, slug_1: str, slug_2: str) -> None:
        customer_1 = Customer.create(slug=slug_1, name="Jerry Seinfeld Inc")
        customer_2 = Customer.create(slug=slug_2, name="Postal Service")
        customer_3 = Customer.create(slug="jpeterman", name="The J. Peterman Company", scm=Customer.Scm.BITBUCKET)
        assert Customer.for_slugs([]) == set()
        assert Customer.for_slugs(["nosuchslug"]) == set()
        assert Customer.for_slugs(["jerry"]) == {customer_1}
        assert Customer.for_slugs(["JERRy"]) == {customer_1}
        assert Customer.for_slugs(["jerry"], scm=Customer.Scm.BITBUCKET) == set()
        assert Customer.for_slugs(["Jerry"], scm=Customer.Scm.BITBUCKET) == set()
        assert Customer.for_slugs(["nosuchslug", "jerry"]) == {customer_1}
        assert Customer.for_slugs(["nosuchslug", "JErry"]) == {customer_1}
        assert Customer.for_slugs(["JERRY", "usps"]) == {customer_1, customer_2}
        assert Customer.for_slugs(["jerrY", "USps"]) == {customer_1, customer_2}
        assert Customer.for_slugs(["jerry", "usps", "jpeterman"]) == {customer_1, customer_2, customer_3}
        assert Customer.for_slugs(["jerrY", "usps", "jPEterman"]) == {customer_1, customer_2, customer_3}
        assert Customer.for_slugs(["jerry", "usps", "jpeterman"], scm=Customer.Scm.GITHUB) == {customer_1, customer_2}
        assert Customer.for_slugs(["Jerry", "Usps", "JPETerman"], scm=Customer.Scm.GITHUB) == {customer_1, customer_2}
        assert Customer.for_slugs(["jerry", "usps", "jpeterman"], scm=Customer.Scm.BITBUCKET) == {customer_3}
        assert Customer.for_slugs(["jerry", "usps", "JPeterman"], scm=Customer.Scm.BITBUCKET) == {customer_3}
        assert Customer.for_slugs(["jerry", "jpeterman"]) == {customer_1, customer_3}
        assert Customer.for_slugs(["JERRy", "jpeterMAn"]) == {customer_1, customer_3}
        assert Customer.for_slugs(["jerry", "jpeterman"], scm=Customer.Scm.GITHUB) == {customer_1}
        assert Customer.for_slugs(["jeRRy", "jpeterman"], scm=Customer.Scm.GITHUB) == {customer_1}
        assert Customer.for_slugs(["jerry", "jpeterman", "nosuchslug"]) == {customer_1, customer_3}
        assert Customer.for_slugs(["Jerry", "JPeterman", "nosuchslug"]) == {customer_1, customer_3}

        customer_1.deactivate()
        assert Customer.for_slugs(["JErry", "jpeterMAn", "nosuchslug"]) == {customer_3}
        assert Customer.for_slugs(["jerry", "jPeterman", "nosuchslug"], scm=Customer.Scm.GITHUB) == set()
        assert Customer.for_slugs(["JERRY", "jpeterman", "nosuchslug"], scm=Customer.Scm.BITBUCKET) == {customer_3}
        assert Customer.for_slugs(["jerry", "JPETERMAN", "nosuchslug"], scm=Customer.Scm.BITBUCKET) == {customer_3}

    def test_for_user_and_slug(self) -> None:
        user_1 = ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")
        user_2 = ToolchainUser.create(username="jerry", email="jerry@seinfeld.com")
        user_3 = ToolchainUser.create(username="kramer", email="kramer@seinfeld.com")
        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer_2 = Customer.create(slug="jpeterman", name="The J. Peterman Company")
        customer_1.add_user(user_1)
        customer_2.add_user(user_2)
        customer_1.add_user(user_3)
        customer_2.add_user(user_3)

        assert Customer.for_user_and_slug(user_api_id=user_1.api_id, slug="jpeterman") is None
        assert Customer.for_user_and_slug(user_api_id=user_1.api_id, slug="jerry") == customer_1

        assert Customer.for_user_and_slug(user_api_id=user_2.api_id, slug="jerry") is None
        assert Customer.for_user_and_slug(user_api_id=user_2.api_id, slug="jpeterman") == customer_2

        assert Customer.for_user_and_slug(user_api_id=user_3.api_id, slug="mandelbaum") is None
        assert Customer.for_user_and_slug(user_api_id=user_3.api_id, slug="jerry") == customer_1
        assert Customer.for_user_and_slug(user_api_id=user_3.api_id, slug="jpeterman") == customer_2

        customer_2.deactivate()
        assert Customer.for_user_and_slug(user_api_id=user_3.api_id, slug="jpeterman") is None

    def test_for_user_and_id(self) -> None:
        user_1 = ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")
        user_2 = ToolchainUser.create(username="jerry", email="jerry@seinfeld.com")
        user_3 = ToolchainUser.create(username="kramer", email="kramer@seinfeld.com")
        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer_2 = Customer.create(slug="jpeterman", name="The J. Peterman Company")
        customer_1.add_user(user_1)
        customer_2.add_user(user_2)
        customer_1.add_user(user_3)
        customer_2.add_user(user_3)

        assert Customer.for_user_and_id(user_api_id=user_1.api_id, customer_id=customer_2.pk) is None
        assert Customer.for_user_and_id(user_api_id=user_1.api_id, customer_id=customer_1.pk) == customer_1

        assert Customer.for_user_and_id(user_api_id=user_2.api_id, customer_id=customer_1.pk) is None
        assert Customer.for_user_and_id(user_api_id=user_2.api_id, customer_id=customer_2.pk) == customer_2

        assert Customer.for_user_and_id(user_api_id=user_3.api_id, customer_id="mandelbaum") is None
        assert Customer.for_user_and_id(user_api_id=user_3.api_id, customer_id=customer_1.pk) == customer_1
        assert Customer.for_user_and_id(user_api_id=user_3.api_id, customer_id=customer_2.pk) == customer_2

        customer_1.deactivate()
        assert Customer.for_user_and_id(user_api_id=user_3.api_id, customer_id=customer_1.pk) is None

    def test_exists_user_and_id(self) -> None:
        user_1 = ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")
        user_2 = ToolchainUser.create(username="jerry", email="jerry@seinfeld.com")
        user_3 = ToolchainUser.create(username="kramer", email="kramer@seinfeld.com")
        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer_2 = Customer.create(slug="jpeterman", name="The J. Peterman Company")
        customer_1.add_user(user_1)
        customer_2.add_user(user_2)
        customer_1.add_user(user_3)
        customer_2.add_user(user_3)

        assert Customer.exists_user_and_id(user_api_id=user_1.api_id, customer_id=customer_2.pk) is False
        assert Customer.exists_user_and_id(user_api_id=user_1.api_id, customer_id=customer_1.pk) is True

        assert Customer.exists_user_and_id(user_api_id=user_2.api_id, customer_id=customer_1.pk) is False
        assert Customer.exists_user_and_id(user_api_id=user_2.api_id, customer_id=customer_2.pk) is True

        assert Customer.exists_user_and_id(user_api_id=user_3.api_id, customer_id="mandelbaum") is False
        assert Customer.exists_user_and_id(user_api_id=user_3.api_id, customer_id=customer_1.pk) is True
        assert Customer.exists_user_and_id(user_api_id=user_3.api_id, customer_id=customer_2.pk) is True

        customer_2.deactivate()
        assert Customer.exists_user_and_id(user_api_id=user_3.api_id, customer_id=customer_2.pk) is False

    @pytest.mark.parametrize("slug", ["jerry", "Jerry", "JeRRY", "JERRY"])
    def test_for_slug(self, slug: str) -> None:
        customer_1 = Customer.create(slug=slug, name="Jerry Seinfeld Inc")
        customer_2 = Customer.create(slug="jpeterman", name="The J. Peterman Company")
        assert Customer.for_slug("jerry1") is None
        assert Customer.for_slug("") is None
        assert Customer.for_slug("jerry") == customer_1
        assert Customer.for_slug("JERRY") == customer_1
        assert Customer.for_slug("jErry") == customer_1
        assert Customer.for_slug("Jerry") == customer_1
        assert Customer.for_slug("jpeterman") == customer_2
        assert Customer.for_slug("jerry").deactivate() is True  # type: ignore
        assert Customer.for_slug("jerry") is None
        assert Customer.for_slug("jerry", include_inactive=True) == customer_1

    def test_customer_state(self) -> None:
        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer_2 = Customer.create(slug="usps", name="Postal Service")
        assert customer_1.is_active is True
        assert customer_1.state == Customer.State.ACTIVE
        assert customer_2.is_active is True
        assert customer_2.state == Customer.State.ACTIVE

        assert customer_1.deactivate() is True
        c1 = Customer.objects.get(id=customer_1.id)
        assert c1.is_active is False
        assert c1.state == Customer.State.INACTIVE
        assert c1.deactivate() is False

        c2 = Customer.objects.get(id=customer_2.id)
        assert c2.is_active is True
        assert c2.state == Customer.State.ACTIVE

    def test_maybe_set_logo(self) -> None:
        customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        assert customer.logo_url == ""
        assert customer.maybe_set_logo("https://jerry.com/logo.png") is True
        assert customer.logo_url == "https://jerry.com/logo.png"
        loaded_customer = Customer.objects.get(id=customer.id)
        assert loaded_customer.logo_url == "https://jerry.com/logo.png"
        assert customer.maybe_set_logo("https://kramer.com/logo.png") is False
        assert customer.logo_url == "https://jerry.com/logo.png"
        loaded_customer = Customer.objects.get(id=customer.id)
        assert loaded_customer.logo_url == "https://jerry.com/logo.png"

    def test_create(self, caplog) -> None:
        customer_1 = Customer.create("jerry", "Jerry Seinfeld", customer_type=Customer.Type.OPEN_SOURCE)
        assert len(caplog.records) == 1
        assert_messages(caplog, "new_customer_created")
        caplog.clear()
        customer_2 = Customer.create("george", "George Costanza", scm=CustomerScmProvider.BITBUCKET)
        assert len(caplog.records) == 1
        assert_messages(caplog, "new_customer_created")
        assert customer_1.customer_type == Customer.Type.OPEN_SOURCE
        assert customer_2.customer_type == Customer.Type.PROSPECT
        assert customer_1.is_internal is False
        assert customer_2.is_internal is False
        assert customer_1.slug == "jerry"
        assert customer_1.name == "Jerry Seinfeld"
        assert customer_1.scm_provider == CustomerScmProvider.GITHUB
        assert customer_1.service_level == Customer.ServiceLevel.FULL_SERVICE
        assert customer_1.is_limited is False
        assert customer_1.is_in_free_trial is False
        assert customer_2.slug == "george"
        assert customer_2.name == "George Costanza"
        assert customer_2.scm_provider == CustomerScmProvider.BITBUCKET
        assert customer_2.service_level == Customer.ServiceLevel.FULL_SERVICE
        assert customer_2.is_limited is False
        assert customer_2.is_in_free_trial is True

    def test_set_service_level(self, django_assert_num_queries, caplog) -> None:
        customer = Customer.create("jerry", "Jerry Seinfeld")
        assert customer.service_level == Customer.ServiceLevel.FULL_SERVICE
        assert customer.is_limited is False
        with django_assert_num_queries(2):
            customer.set_service_level(Customer.ServiceLevel.LIMITED)
        assert_messages(caplog, "update_customer: service_level for")
        loaded = Customer.objects.get(id=customer.id)
        assert customer.service_level == loaded.service_level == Customer.ServiceLevel.LIMITED
        assert customer.is_limited is True
        assert loaded.is_limited is True
        caplog.clear()
        with django_assert_num_queries(2):
            customer.set_service_level(Customer.ServiceLevel.FULL_SERVICE)
        assert_messages(caplog, "update_customer: service_level for")
        loaded = Customer.objects.get(id=customer.id)
        assert customer.service_level == loaded.service_level == Customer.ServiceLevel.FULL_SERVICE
        assert customer.is_limited is False
        assert loaded.is_limited is False

    def test_set_service_level_no_op(self, django_assert_num_queries) -> None:
        customer = Customer.create("jerry", "Jerry Seinfeld")
        assert customer.service_level == Customer.ServiceLevel.FULL_SERVICE
        with django_assert_num_queries(0):
            customer.set_service_level(Customer.ServiceLevel.FULL_SERVICE)
        loaded = Customer.objects.get(id=customer.id)
        assert loaded.service_level == Customer.ServiceLevel.FULL_SERVICE
        customer = loaded
        customer.set_service_level(Customer.ServiceLevel.LIMITED)
        with django_assert_num_queries(0):
            customer.set_service_level(Customer.ServiceLevel.LIMITED)
        loaded = Customer.objects.get(id=customer.id)
        assert loaded.service_level == Customer.ServiceLevel.LIMITED

    def test_create_duplicate_slugs(self) -> None:
        Customer.create("JerrY", "Jerry Seinfeld")
        with pytest.raises(CustomerSaveError, match="slug 'JERRY' already used by"):
            # Django admin (toolshed) uses this code path
            Customer.objects.create(slug="JERRY", name="Seinfeld")
        assert Customer.objects.count() == 1
        with pytest.raises(CustomerSaveError, match="slug 'jerry' already used by"):
            Customer.create(slug="jerry", name="Seinfeld")
        assert Customer.objects.count() == 1

    def test_slug_update(self) -> None:
        customer_1 = Customer.create("jerry", "Jerry Seinfeld")
        customer_2 = Customer.create("george", "George Costanza", scm=CustomerScmProvider.BITBUCKET)
        customer_1.slug = "Jerry"
        customer_1.save()
        loaded_customer_1 = Customer.objects.get(id=customer_1.id)
        assert loaded_customer_1.slug == "Jerry"
        customer_2.slug = "frank"
        customer_2.save()
        loaded_customer_2 = Customer.objects.get(id=customer_2.id)
        assert loaded_customer_2.slug == "frank"

    def test_prevent_slug_update_duplicate(self) -> None:
        Customer.create("jerry", "Jerry Seinfeld")
        customer_2 = Customer.create("george", "George Costanza", scm=CustomerScmProvider.BITBUCKET)

        customer_2.slug = "jERRY"
        with pytest.raises(CustomerSaveError, match="slug 'jERRY' already used by"):
            customer_2.save()
        loaded_customer_2 = Customer.objects.get(id=customer_2.id)
        assert loaded_customer_2.slug == "george"

    def test_set_name(self) -> None:
        customer = Customer.create("jerry", "Jerry Seinfeld")
        assert customer.set_name("Jerry Seinfeld") is False
        assert Customer.objects.get(id=customer.id).name == "Jerry Seinfeld"
        assert customer.set_name("Good night, Jugdish") is True
        assert Customer.objects.get(id=customer.id).name == "Good night, Jugdish"

    def test_set_customer_type(self, django_assert_num_queries, caplog) -> None:
        customer = Customer.create("jerry", "Jerry Seinfeld", customer_type=Customer.Type.PROSPECT)
        with django_assert_num_queries(0):
            customer.set_type(Customer.Type.PROSPECT)
        loaded = Customer.objects.get(id=customer.pk)
        assert loaded.customer_type == Customer.Type.PROSPECT
        assert loaded.is_open_source is False
        customer = loaded
        with django_assert_num_queries(2):
            customer.set_type(Customer.Type.CUSTOMER)
        assert_messages(caplog, "update_customer: type for")
        loaded = Customer.objects.get(id=customer.pk)
        assert loaded.customer_type == Customer.Type.CUSTOMER
        assert loaded.is_open_source is False

    @pytest.mark.parametrize("customer_type", [Customer.Type.OPEN_SOURCE, Customer.Type.INTERNAL])
    def test_set_customer_type_invalid_type(self, customer_type, django_assert_num_queries):
        def _assert_transition(cus, cus_type):
            with django_assert_num_queries(0), pytest.raises(
                ToolchainAssertion, match="Not allowed to transition customer of type"
            ):
                cus.set_type(cus_type)

        prospect = Customer.create("jerry", "Jerry Seinfeld", customer_type=Customer.Type.PROSPECT)
        customer = Customer.create(slug="usps", name="Postal Service", customer_type=customer_type)
        _assert_transition(prospect, customer_type)
        _assert_transition(customer, Customer.Type.PROSPECT)
        _assert_transition(customer, Customer.Type.CUSTOMER)

    def test_get_for_id_or_none(self) -> None:
        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer_2 = Customer.create(slug="jpeterman", name="The J. Peterman Company")
        assert Customer.get_for_id_or_none(customer_id="bob", include_inactive=True) is None
        assert Customer.get_for_id_or_none(customer_id="bob", include_inactive=False) is None
        assert Customer.get_for_id_or_none(customer_id=customer_1.id) == customer_1
        assert Customer.get_for_id_or_none(customer_id=customer_1.id, include_inactive=True) == customer_1

        assert Customer.get_for_id_or_none(customer_id=customer_2.id) == customer_2
        assert Customer.get_for_id_or_none(customer_id=customer_2.id, include_inactive=True) == customer_2

        customer_2.deactivate()
        assert Customer.get_for_id_or_none(customer_id=customer_2.id) is None
        assert Customer.get_for_id_or_none(customer_id=customer_2.id, include_inactive=True) == customer_2

    def test_get_internal_customers_for_ids(self) -> None:
        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc", customer_type=Customer.Type.INTERNAL)
        customer_2 = Customer.create(slug="jpeterman", name="The J. Peterman Company")
        customer_3 = Customer.create(slug="usps", name="Postal Service", customer_type=Customer.Type.INTERNAL)
        internal_customers = Customer.get_internal_customers_for_ids(
            customer_ids={customer_1.id, customer_2.id, customer_3.id}
        )
        assert len(internal_customers) == 2
        assert set(internal_customers) == {customer_1, customer_3}


@pytest.mark.django_db()
class TestRepoModel:
    def test_get_or_none_for_slug(self) -> None:
        user_1 = ToolchainUser.create(username="kramer", email="kramer@seinfeld.com")
        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer_1.add_user(user_1)
        repo_1 = Repo.create("cookie", customer_1, "Look to the cookie")

        user_2 = ToolchainUser.create(username="newman", email="newman@seinfeld.com")
        customer_2 = Customer.create(slug="usps", name="Postal Service")
        customer_2.add_user(user_2)
        repo_2 = Repo.create("mailbox", customer_2, "Mail never stops")

        user_3 = ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")

        assert Repo.get_or_none_for_slug("mailbox", user_2) == repo_2
        assert Repo.get_or_none_for_slug("cookie", user_1) == repo_1
        assert Repo.get_or_none_for_slug("cookie", user_2) is None
        assert Repo.get_or_none_for_slug("mailbox", user_1) is None
        assert Repo.get_or_none_for_slug("mailbox", user_3) is None
        assert Repo.get_or_none_for_slug("soup", user_1) is None
        assert Repo.get_or_none_for_slug("soup", user_3) is None
        repo_1.deactivate()
        assert Repo.get_or_none_for_slug("cookie", user_1) is None

    def test_with_api_ids(self) -> None:
        customer_0 = Customer.create(slug="kramer", name="Kramerica Industries")
        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        repo_1a = Repo.create("cookie", customer_1, "Look to the cookie")
        repo_1b = Repo.create("babka", customer_1, "Cinemon babka")

        customer_2 = Customer.create(slug="usps", name="Postal Service")
        repo_2a = Repo.create("newman", customer_2, "postal employee")
        assert Repo.with_api_ids(customer_id=customer_0.pk, repo_ids={repo_1a.pk, repo_1b.pk, repo_2a.pk}) == tuple()
        assert set(Repo.with_api_ids(customer_id=customer_1.pk, repo_ids=[repo_1a.pk, repo_1b.pk, repo_2a.pk])) == {
            repo_1a,
            repo_1b,
        }
        assert set(Repo.with_api_ids(customer_id=customer_2.pk, repo_ids=(repo_1a.pk, repo_1b.pk, repo_2a.pk))) == {
            repo_2a
        }
        repo_1b.deactivate()
        assert set(Repo.with_api_ids(customer_id=customer_1.pk, repo_ids=[repo_1a.pk, repo_1b.pk, repo_2a.pk])) == {
            repo_1a,
        }

    def test_with_api_ids_no_customer_id(self) -> None:
        Customer.create(slug="kramer", name="Kramerica Industries")
        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        repo_1a = Repo.create("cookie", customer_1, "Look to the cookie")
        repo_1b = Repo.create("babka", customer_1, "Cinemon babka")
        customer_2 = Customer.create(slug="usps", name="Postal Service")
        repo_2a = Repo.create("newman", customer_2, "postal employee")

        assert set(Repo.with_api_ids(repo_ids={repo_1a.pk, repo_1b.pk, "bob"})) == {repo_1a, repo_1b}
        assert set(Repo.with_api_ids(repo_ids={repo_1a.pk, repo_2a.pk, "bob"})) == {repo_1a, repo_2a}

    def test_exists_for_customer(self) -> None:
        customer_0 = Customer.create(slug="kramer", name="Kramerica Industries")
        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        repo_1a = Repo.create("cookie", customer_1, "Look to the cookie")
        repo_1b = Repo.create("babka", customer_1, "Cinemon babka")

        customer_2 = Customer.create(slug="usps", name="Postal Service")
        repo_2a = Repo.create("newman", customer_2, "postal employee")

        assert Repo.exists_for_customer(repo_id=repo_1a.id, customer_id=customer_0.id) is False
        assert Repo.exists_for_customer(repo_id=repo_1b.id, customer_id=customer_0.id) is False

        assert Repo.exists_for_customer(repo_id=repo_1a.id, customer_id=customer_1.id) is True
        assert Repo.exists_for_customer(repo_id=repo_1b.id, customer_id=customer_1.id) is True
        assert Repo.exists_for_customer(repo_id=repo_1a.id, customer_id=customer_2.id) is False

        assert Repo.exists_for_customer(repo_id=repo_2a.id, customer_id=customer_0.id) is False
        assert Repo.exists_for_customer(repo_id=repo_2a.id, customer_id=customer_1.id) is False
        assert Repo.exists_for_customer(repo_id=repo_2a.id, customer_id=customer_2.id) is True
        repo_2a.deactivate()
        assert Repo.exists_for_customer(repo_id=repo_2a.id, customer_id=customer_2.id) is False

    def test_get_by_slug_and_customer_id(self, django_assert_num_queries) -> None:
        customer_0 = Customer.create(slug="kramer", name="Kramerica Industries")
        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        repo_1a = Repo.create("cookie", customer_1, "Look to the cookie")
        repo_1b = Repo.create("babka", customer_1, "Cinemon babka")
        assert Repo.get_by_slug_and_customer_id(customer_id=customer_0.id, slug="cookie") is None
        with django_assert_num_queries(1):
            loaded_repo = Repo.get_by_slug_and_customer_id(customer_id=customer_1.id, slug="cookie")
            assert loaded_repo is not None
            assert loaded_repo.slug == "cookie"
            assert loaded_repo.customer.slug == "jerry"

        assert loaded_repo == repo_1a
        assert Repo.get_by_slug_and_customer_id(customer_id=customer_1.id, slug="babka") == repo_1b
        repo_1a.deactivate()
        assert Repo.get_by_slug_and_customer_id(customer_id=customer_1.id, slug="cookie") is None
        assert (
            Repo.get_by_slug_and_customer_id(customer_id=customer_1.id, slug="babka", include_inactive=True) == repo_1b
        )

    def test_get_for_slugs_or_none(self) -> None:
        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer_2 = Customer.create(slug="usps", name="Postal Service")
        repo_1 = Repo.create("cookie", customer_1, "Look to the cookie")
        repo_2 = Repo.create("mailbox", customer_2, "Mail never stops")

        assert Repo.get_for_slugs_or_none(customer_slug="jerry", repo_slug="mailbox") is None
        assert Repo.get_for_slugs_or_none(customer_slug="jerry", repo_slug="cookie") == repo_1
        assert Repo.get_for_slugs_or_none(customer_slug="usps", repo_slug="mailbox") == repo_2

        customer_2.deactivate()
        assert Repo.get_for_slugs_or_none(customer_slug="usps", repo_slug="mailbox") is None

    def test_get_for_slugs_or_none_include_inactive(self) -> None:
        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer_2 = Customer.create(slug="usps", name="Postal Service")
        repo_1 = Repo.create("cookie", customer_1, "Look to the cookie")
        repo_2 = Repo.create("mailbox", customer_2, "Mail never stops")

        with pytest.raises(Repo.DoesNotExist, match="Repo matching query does not exist."):
            Repo.get_for_slugs_or_none(customer_slug="jerry", repo_slug="mailbox", include_inactive=True)
        assert Repo.get_for_slugs_or_none(customer_slug="jerry", repo_slug="cookie", include_inactive=True) == repo_1
        assert Repo.get_for_slugs_or_none(customer_slug="usps", repo_slug="mailbox", include_inactive=True) == repo_2

        customer_2.deactivate()
        assert Repo.get_for_slugs_or_none(customer_slug="usps", repo_slug="mailbox", include_inactive=True) == repo_2

    def test_create(self, caplog) -> None:
        customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        repo = Repo.create(slug="newman", customer=customer, name="USPS")
        assert repo.customer_id == customer.id
        assert repo.slug == "newman"
        assert repo.name == "USPS"
        assert repo.state == RepoState.ACTIVE
        assert repo.is_active is True
        assert repo.visibility == Repo.Visibility.PRIVATE
        assert_messages(caplog, "repo_created")

    def test_create_via_model_api(self, caplog) -> None:
        customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        repo = Repo.objects.create(
            slug="bob",
            customer=customer,
            name="Sacamano",
        )
        assert repo.customer_id == customer.id
        assert repo.slug == "bob"
        assert repo.name == "Sacamano"
        assert repo.state == RepoState.ACTIVE
        assert repo.visibility == Repo.Visibility.PRIVATE
        assert repo.is_active is True
        assert_messages(caplog, "repo_created")

    def test_create_existing(self, caplog) -> None:
        customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        repo = Repo.create(slug="newman", customer=customer, name="USPS")
        assert_messages(caplog, "repo_created")
        caplog.clear()
        repo_2 = Repo.create(slug="newman", customer=customer, name="mailman")
        assert len(caplog.messages) == 0
        assert repo_2.customer_id == customer.id
        assert repo_2.slug == "newman"
        assert repo_2.name == "USPS"
        assert repo.id == repo_2.id
        assert repo.state == RepoState.ACTIVE
        assert repo.is_active is True
        assert repo_2.state == RepoState.ACTIVE
        assert repo_2.is_active is True
        assert repo.visibility == Repo.Visibility.PRIVATE

    def test_create_duplicate_slug(self) -> None:
        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer_2 = Customer.create(slug="usps", name="Postal Service")
        Repo.create(slug="newman", customer=customer_1, name="USPS")
        Repo.create(slug="newman", customer=customer_2, name="mailman")
        assert Repo.objects.count() == 2
        repo_1 = Repo.get_by_slug_and_customer_id(customer_id=customer_1.id, slug="newman")
        repo_2 = Repo.get_by_slug_and_customer_id(customer_id=customer_2.id, slug="newman")
        assert repo_1 is not None
        assert repo_1.slug == "newman"
        assert repo_1.name == "USPS"
        assert repo_1.is_active is True
        assert repo_1.customer_id == customer_1.pk
        assert repo_1.visibility == Repo.Visibility.PRIVATE

        assert repo_2 is not None
        assert repo_2.slug == "newman"
        assert repo_2.name == "mailman"
        assert repo_2.is_active is True
        assert repo_2.customer_id == customer_2.id
        assert repo_2.visibility == Repo.Visibility.PRIVATE

    def test_create_duplicate_slug_same_customer(self) -> None:
        customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        Customer.create(slug="usps", name="Postal Service")
        repo_1 = Repo.create(slug="newman", customer=customer, name="USPS")
        repo_2 = Repo.create(slug="newman", customer=customer, name="mailman")
        assert Repo.objects.count() == 1
        repo = Repo.objects.first()
        assert repo == repo_1 == repo_2
        assert repo.slug == "newman"
        assert repo.name == "USPS"
        assert repo.is_active is True

    def test_create_duplicate_slug_same_customer_inactive_repo(self) -> None:
        customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        Customer.create(slug="usps", name="Postal Service")
        Repo.create(slug="newman", customer=customer, name="USPS").deactivate()
        with pytest.raises(RepoCreationError, match="Repo with slug='newman' already exists"):
            Repo.create(slug="newman", customer=customer, name="mailman")
        assert Repo.objects.count() == 1
        repo = Repo.objects.first()
        assert repo.slug == "newman"
        assert repo.name == "USPS"
        assert repo.is_active is False

    def _create_repos(self, customer, prefix: str, count: int):
        for i in range(count):
            repo = Repo.create(slug=f"repo_{prefix}_{i+1}", customer=customer, name=f"Test repo #{i+1}")
            assert repo.state == RepoState.ACTIVE

    def test_max_repo_limit(self) -> None:
        max_repos = Repo.MAX_CUSTOMER_REPOS
        assert max_repos == 25
        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer_2 = Customer.create(slug="usps", name="Postal Service")
        self._create_repos(customer_1, "puddy", max_repos)
        assert Repo.objects.count() == max_repos
        # Doesn't create a new repo
        repo = Repo.create(slug="repo_puddy_6", customer=customer_1, name="Test repo")
        assert Repo.objects.count() == max_repos
        assert repo.name == "Test repo #6"
        assert repo.slug == "repo_puddy_6"
        assert repo.customer_id == customer_1.id
        with pytest.raises(RepoCreationError, match="Max number of repos for customer=jerry exceeded"):
            Repo.create(slug="repo_60", customer=customer_1, name="Test max repo")
        assert Repo.objects.count() == max_repos
        self._create_repos(customer_2, "pit", 4)
        assert Repo.objects.count() == max_repos + 4
        assert Repo.objects.filter(customer_id=customer_1.id).count() == max_repos
        assert Repo.objects.filter(customer_id=customer_2.id).count() == 4

    def test_max_repo_limit_with_inactive_repos(self) -> None:
        customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        self._create_repos(customer, "jerk-store", 25)
        assert Repo.objects.count() == 25
        with pytest.raises(RepoCreationError, match="Max number of repos for customer=jerry exceeded"):
            Repo.create(slug="repo_60", customer=customer, name="Test max repo")
        assert Repo.objects.count() == 25
        Repo.objects.first().deactivate()
        Repo.create(slug="repo_62", customer=customer, name="Test max repo")
        assert Repo.objects.count() == 26
        assert Repo.base_qs().count() == 25
        repo = Repo.objects.get(slug="repo_62")
        assert repo.state == RepoState.ACTIVE
        assert repo.is_active is True

    def test_create_repo_with_inactive_slug(self) -> None:
        customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        repo = Repo.create(slug="come-back", customer=customer, name="Best seller")
        repo.deactivate()
        with pytest.raises(RepoCreationError, match="Repo with slug='come-back' already exists"):
            Repo.create(slug="come-back", customer=customer, name="Jerk Store")
        loaded_repo = Repo.objects.get(slug="come-back")
        assert loaded_repo.state == RepoState.INACTIVE
        assert loaded_repo.is_active is False
        assert loaded_repo.name == "Best seller"
        assert loaded_repo.customer_id == customer.id
        assert loaded_repo.id == repo.id

    def test_slug_uniqueness(self) -> None:
        customer_1 = Customer.create(slug="kramer", name="Kramerica Industries")
        customer_2 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        Repo.create("cookie", customer_1, "Look to the cookie")
        assert Repo.objects.count() == 1
        Repo.objects.create(slug="cookie", customer_id=customer_2.id, name="Jerk-Store")
        assert Repo.objects.count() == 2
        with pytest.raises(
            IntegrityError, match='duplicate key value violates unique constraint "unique_customer_repo_slug"'
        ), transaction.atomic():
            Repo.objects.create(slug="cookie", customer_id=customer_1.id, name="Mandelbaum")
        assert Repo.objects.count() == 2
        repo_1 = Repo.get_by_slug_and_customer_id(customer_1.id, slug="cookie")
        assert repo_1 is not None
        assert repo_1.name == "Look to the cookie"
        repo_2 = Repo.get_by_slug_and_customer_id(customer_2.id, slug="cookie")
        assert repo_2 is not None
        assert repo_2.name == "Jerk-Store"

    def to_full_slugs(self, repos) -> list[str]:
        return [f"{repo.customer.slug}/{repo.slug}" for repo in repos]

    def test_for_customer(self, django_assert_num_queries) -> None:
        def get_slugs(customer):
            with django_assert_num_queries(1):
                return self.to_full_slugs(Repo.for_customer(customer))

        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer_2 = Customer.create(slug="usps", name="Postal Service")
        customer_3 = Customer.create(slug="nbc", name="NBC")
        Repo.create("cookie", customer_1, "Look to the cookie")
        Repo.create("mailbox", customer_1, "Mail never stops")
        Repo.create("submarine", customer_2, "Turn your key")
        Repo.create("buzzer", customer_2, "strongbox")

        assert get_slugs(customer_1) == [
            "jerry/cookie",
            "jerry/mailbox",
        ]
        assert get_slugs(customer_2) == [
            "usps/buzzer",
            "usps/submarine",
        ]

        assert get_slugs(customer_3) == []
        Repo.create("bob", customer_3, "Mail never stops")
        assert get_slugs(customer_3) == ["nbc/bob"]

    def test_for_user_with_slugs(self, django_assert_num_queries) -> None:
        def get_slugs(user):
            with django_assert_num_queries(1):
                return self.to_full_slugs(Repo.for_user(user))

        user_1 = ToolchainUser.create(username="kramer", email="kramer@seinfeld.com")
        user_2 = ToolchainUser.create(username="newman", email="newman@seinfeld.com")
        user_3 = ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")
        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer_2 = Customer.create(slug="usps", name="Postal Service")
        customer_3 = Customer.create(slug="nbc", name="NBC")
        customer_1.add_user(user_2)
        customer_1.add_user(user_1)
        customer_2.add_user(user_1)
        Repo.create("cookie", customer_1, "Look to the cookie")
        Repo.create("mailbox", customer_1, "Mail never stops")
        Repo.create("kx", customer_2, "j")
        Repo.create("dx", customer_2, "m")
        Repo.create("bob", customer_3, "Mail never stops")
        assert len(user_2.customers_ids) == 1

        assert get_slugs(user_1) == ["jerry/cookie", "usps/dx", "usps/kx", "jerry/mailbox"]
        assert get_slugs(user_2) == ["jerry/cookie", "jerry/mailbox"]
        assert get_slugs(user_3) == []

    def test_get_for_id_and_user_or_none(self, django_assert_num_queries) -> None:
        user_1 = ToolchainUser.create(username="kramer", email="kramer@seinfeld.com")
        user_2 = ToolchainUser.create(username="newman", email="newman@seinfeld.com")
        customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer.add_user(user_1)
        repo_id = Repo.create("cookie", customer, "Look to the cookie").id

        with django_assert_num_queries(2):
            repo = Repo.get_for_id_and_user_or_none(repo_id=repo_id, user=user_1)
            assert repo.slug == "cookie"
            assert repo.customer.slug == "jerry"
        with django_assert_num_queries(0):
            assert repo.full_name == "jerry/cookie"

        with django_assert_num_queries(1):
            assert Repo.get_for_id_and_user_or_none(repo_id=repo_id, user=user_2) is None

    def test_get_for_id_and_or_none(self, django_assert_num_queries) -> None:
        customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        repo = Repo.create("cookie", customer, "Look to the cookie")

        with django_assert_num_queries(1):
            loaded_repo = Repo.get_for_id_or_none(repo_id=repo.id)
            assert loaded_repo.slug == "cookie"
            assert loaded_repo.customer.slug == "jerry"

        with django_assert_num_queries(1):
            loaded_repo = Repo.get_for_id_or_none(repo_id=repo.id, include_inactive=True)
            assert loaded_repo.slug == "cookie"
            assert loaded_repo.customer.slug == "jerry"
        with django_assert_num_queries(0):
            assert repo.full_name == "jerry/cookie"
        repo.deactivate()

        with django_assert_num_queries(1):
            assert Repo.get_for_id_or_none(repo_id=repo.id) is None

        with django_assert_num_queries(1):
            assert Repo.get_for_id_or_none(repo_id=repo.id, include_inactive=False) is None

        with django_assert_num_queries(1):
            loaded_repo = Repo.get_for_id_or_none(repo_id=repo.id, include_inactive=True)
            assert loaded_repo.slug == "cookie"
            assert loaded_repo.customer.slug == "jerry"

    def test_get_or_404_for_slugs_and_user(self, django_assert_num_queries) -> None:
        user_1 = ToolchainUser.create(username="kramer", email="kramer@seinfeld.com")
        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer_1.add_user(user_1)
        repo_1 = Repo.create("cookie", customer_1, "Look to the cookie")

        user_2 = ToolchainUser.create(username="newman", email="newman@seinfeld.com")
        customer_2 = Customer.create(slug="usps", name="Postal Service")
        customer_2.add_user(user_2)
        repo_2 = Repo.create("mailbox", customer_2, "Mail never stops")

        user_3 = ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")

        with django_assert_num_queries(2):
            loaded_repo_2 = Repo.get_or_404_for_slugs_and_user(repo_slug="mailbox", customer_slug="usps", user=user_2)

        with django_assert_num_queries(2):
            loaded_repo_1 = Repo.get_or_404_for_slugs_and_user(repo_slug="cookie", customer_slug="jerry", user=user_1)

        with django_assert_num_queries(0):  # Make sure Repo.customer is pre-loaded.
            assert loaded_repo_2 == repo_2
            assert loaded_repo_1 == repo_1
            assert loaded_repo_1.customer.id == customer_1.id
            assert loaded_repo_1.customer.slug == "jerry"
            assert loaded_repo_1.full_name == "jerry/cookie"
            assert loaded_repo_2.full_name == "usps/mailbox"

        with pytest.raises(Http404):
            Repo.get_or_404_for_slugs_and_user(repo_slug="cookie", customer_slug="jerry", user=user_2)

        with pytest.raises(Http404):
            Repo.get_or_404_for_slugs_and_user(repo_slug="mailbox", customer_slug="usps", user=user_1)

        with pytest.raises(Http404):
            Repo.get_or_404_for_slugs_and_user(repo_slug="mailbox", customer_slug="usps", user=user_3)

        with pytest.raises(Http404):
            Repo.get_or_404_for_slugs_and_user(repo_slug="soup", customer_slug="jerry", user=user_1)

        with pytest.raises(Http404):
            Repo.get_or_404_for_slugs_and_user(repo_slug="soup", customer_slug="usps", user=user_3)

        customer_1.deactivate()
        with pytest.raises(Http404):
            Repo.get_or_404_for_slugs_and_user(repo_slug="cookie", customer_slug="jerry", user=user_1)

        repo_2.deactivate()
        with pytest.raises(Http404):
            Repo.get_or_404_for_slugs_and_user(repo_slug="mailbox", customer_slug="usps", user=user_2)

    def test_get_or_none_for_slugs_and_user(self, django_assert_num_queries) -> None:
        user_1 = ToolchainUser.create(username="kramer", email="kramer@seinfeld.com")
        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer_1.add_user(user_1)
        repo_1 = Repo.create("cookie", customer_1, "Look to the cookie")

        user_2 = ToolchainUser.create(username="newman", email="newman@seinfeld.com")
        customer_2 = Customer.create(slug="usps", name="Postal Service")
        customer_2.add_user(user_2)
        repo_2 = Repo.create("mailbox", customer_2, "Mail never stops")

        user_3 = ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")

        with django_assert_num_queries(2):
            loaded_repo_2 = Repo.get_or_none_for_slugs_and_user(repo_slug="mailbox", customer_slug="usps", user=user_2)

        with django_assert_num_queries(2):
            loaded_repo_1 = Repo.get_or_none_for_slugs_and_user(repo_slug="cookie", customer_slug="jerry", user=user_1)

        with django_assert_num_queries(0):  # Make sure Repo.customer is pre-loaded.
            assert loaded_repo_2 == repo_2
            assert loaded_repo_1 == repo_1
            assert loaded_repo_1.customer.id == customer_1.id
            assert loaded_repo_1.customer.slug == "jerry"
            assert loaded_repo_2.customer.slug == "usps"

        assert Repo.get_or_none_for_slugs_and_user(repo_slug="cookie", customer_slug="jerry", user=user_2) is None

        assert Repo.get_or_none_for_slugs_and_user(repo_slug="mailbox", customer_slug="usps", user=user_1) is None

        assert Repo.get_or_none_for_slugs_and_user(repo_slug="mailbox", customer_slug="usps", user=user_3) is None

        assert Repo.get_or_none_for_slugs_and_user(repo_slug="soup", customer_slug="jerry", user=user_1) is None

        assert Repo.get_or_none_for_slugs_and_user(repo_slug="soup", customer_slug="usps", user=user_3) is None

        customer_1.deactivate()
        assert Repo.get_or_none_for_slugs_and_user(repo_slug="cookie", customer_slug="jerry", user=user_1) is None

        repo_2.deactivate()
        assert Repo.get_or_none_for_slugs_and_user(repo_slug="mailbox", customer_slug="usps", user=user_2) is None

    def test_get_by_ids_and_user_or_404(self, django_assert_num_queries) -> None:
        user_1 = ToolchainUser.create(username="kramer", email="kramer@seinfeld.com")
        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer_1.add_user(user_1)
        repo_1 = Repo.create("cookie", customer_1, "Look to the cookie")

        user_2 = ToolchainUser.create(username="newman", email="newman@seinfeld.com")
        customer_2 = Customer.create(slug="usps", name="Postal Service")
        customer_2.add_user(user_2)
        repo_2 = Repo.create("mailbox", customer_2, "Mail never stops")

        user_3 = ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")

        with django_assert_num_queries(2):
            loaded_repo_2 = Repo.get_by_ids_and_user_or_404(repo_id=repo_2.id, customer_id=customer_2.id, user=user_2)
        with django_assert_num_queries(2):
            loaded_repo_1 = Repo.get_by_ids_and_user_or_404(repo_id=repo_1.id, customer_id=customer_1.id, user=user_1)
        assert loaded_repo_1 == repo_1
        assert loaded_repo_2 == repo_2

        with django_assert_num_queries(0):  # Make sure Repo.customer is pre-loaded.
            assert loaded_repo_2 == repo_2
            assert loaded_repo_1 == repo_1
            assert loaded_repo_1.customer.id == customer_1.id
            assert loaded_repo_1.customer.slug == "jerry"
            assert loaded_repo_2.customer.slug == "usps"
        with pytest.raises(Http404):
            Repo.get_by_ids_and_user_or_404(repo_id=repo_1.id, customer_id=customer_1.id, user=user_2)

        with pytest.raises(Http404):
            Repo.get_by_ids_and_user_or_404(repo_id=repo_2.id, customer_id=customer_2.id, user=user_1)

        with pytest.raises(Http404):
            Repo.get_by_ids_and_user_or_404(repo_id=repo_2.id, customer_id=customer_2.id, user=user_3)

        with pytest.raises(Http404):
            Repo.get_by_ids_and_user_or_404(repo_id="bob", customer_id=customer_1.id, user=user_1)

        with pytest.raises(Http404):
            Repo.get_by_ids_and_user_or_404(repo_id="dob", customer_id=customer_2.id, user=user_3)

        customer_1.deactivate()
        with pytest.raises(Http404):
            Repo.get_by_ids_and_user_or_404(repo_id=repo_1.id, customer_id=customer_1.id, user=user_1)

        repo_2.deactivate()
        with pytest.raises(Http404):
            Repo.get_by_ids_and_user_or_404(repo_id=repo_2.id, customer_id=customer_2.id, user=user_2)

    def test_for_customer_id(self, django_assert_num_queries) -> None:
        def get_repos(customer: Customer, include_inactive: bool):
            with django_assert_num_queries(1):
                return list(Repo.for_customer_id(customer.id, include_inactive=include_inactive))

        customer_1 = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer_2 = Customer.create(slug="usps", name="Postal Service")
        customer_3 = Customer.create(slug="nbc", name="NBC")
        r1_1 = Repo.create("cookie", customer_1, "Look to the cookie")
        r2_1 = Repo.create("mailbox", customer_1, "Mail never stops")
        r1_2 = Repo.create("submarine", customer_2, "Turn your key")
        r2_2 = Repo.create("buzzer", customer_2, "strongbox")

        assert (
            get_repos(customer_1, include_inactive=True)
            == get_repos(customer_1, include_inactive=False)
            == [r1_1, r2_1]
        )
        assert get_repos(customer_2, include_inactive=True) == [r2_2, r1_2]
        r1_1.deactivate()
        assert get_repos(customer_1, include_inactive=True) == [r2_1, r1_1]
        assert get_repos(customer_1, include_inactive=False) == [r2_1]
        assert not get_repos(customer_3, include_inactive=True)
        r3 = Repo.create("bob", customer_3, "Mail never stops")
        assert get_repos(customer_3, include_inactive=True) == [r3]

    def test_activate(self) -> None:
        customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        repo = Repo.create("cookie", customer, "Look to the cookie")
        assert repo.is_active is True
        repo.activate()  # no-op
        assert repo.is_active is True
        assert Repo.objects.get(id=repo.id).is_active is True
        repo.deactivate()
        assert Repo.objects.get(id=repo.id).is_active is False
        repo = Repo.objects.get(id=repo.id)
        assert repo.is_active is False
        repo.activate()
        assert repo.is_active is True
        assert Repo.objects.get(id=repo.id).is_active is True

    def test_allow_repo_activation(self) -> None:
        max_repos = Repo.MAX_CUSTOMER_REPOS
        customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        assert Repo.allow_repo_activation(customer_id=customer.id) is True
        self._create_repos(customer, "david", max_repos)
        assert Repo.objects.count() == max_repos
        assert Repo.allow_repo_activation(customer_id=customer.id) is False
        Repo.objects.filter(customer_id=customer.id).first().deactivate()
        assert Repo.allow_repo_activation(customer_id=customer.id) is True

    def test_get_or_none(self, django_assert_num_queries) -> None:
        customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        repo_id = Repo.create("cookie", customer, "Look to the cookie").id
        with django_assert_num_queries(1):  # make sure we don't do another roundtrip when repo.customer is accessed.
            repo = Repo.get_or_none(id=repo_id)
            assert repo is not None
            assert repo.customer_id == customer.id
            assert repo.customer.name == "Jerry Seinfeld Inc"
            assert repo.customer.is_active is True
            assert repo.customer.slug == "jerry"

        with django_assert_num_queries(1):
            repo = Repo.get_or_none(id="cookie")
            assert repo is None


@pytest.mark.django_db()
class TestAllocatedRefreshToken:
    @pytest.fixture()
    def user(self) -> ToolchainUser:
        return ToolchainUser.create(username="kenny", email="kenny@seinfeld.com")

    def test_allocate_api_token(self, user: ToolchainUser) -> None:
        now = utcnow()
        assert AllocatedRefreshToken.objects.count() == 0
        token_id = AllocatedRefreshToken.allocate_api_token(
            user_api_id=user.api_id,
            issued_at=now,
            expires_at=now + datetime.timedelta(minutes=20),
            description="festivus",
            repo_id="jerry",
            audience=AccessTokenAudience.BUILDSENSE_API,
        )
        assert AllocatedRefreshToken.objects.count() == 1
        token = AllocatedRefreshToken.objects.first()
        assert token.id == token_id
        assert token.expires_at == now + datetime.timedelta(minutes=20)
        assert token.issued_at == now
        assert token.last_seen is None
        assert token.description == "festivus"
        assert token.state == AllocatedRefreshToken.State.ACTIVE
        assert token.usage == AllocatedRefreshToken.Usage.API
        assert token.repo_id == "jerry"
        assert token.audiences == AccessTokenAudience.BUILDSENSE_API

    def test_max_api_tokens(self, user: ToolchainUser) -> None:
        now = utcnow()
        assert AllocatedRefreshToken.objects.count() == 0
        for delta in range(0, AllocatedRefreshToken._MAX_TOKENS_PER_USER[AccessTokenUsage.API]):
            AllocatedRefreshToken.allocate_api_token(
                user_api_id=user.api_id,
                issued_at=now,
                expires_at=now + datetime.timedelta(minutes=1 + delta),
                description="festivus",
                repo_id="jerry",
                audience=AccessTokenAudience.BUILDSENSE_API,
            )
        assert (
            AllocatedRefreshToken.objects.count()
            == AllocatedRefreshToken._MAX_TOKENS_PER_USER[AccessTokenUsage.API]
            == 25
        )
        with pytest.raises(MaxActiveTokensReachedError, match="Max number of active tokens reached"):
            AllocatedRefreshToken.allocate_api_token(
                user_api_id=user.api_id,
                issued_at=now,
                expires_at=now + datetime.timedelta(minutes=3),
                description="festivus",
                repo_id="jerry",
                audience=AccessTokenAudience.CACHE_RW | AccessTokenAudience.CACHE_RO,
            )
        assert (
            AllocatedRefreshToken.objects.count()
            == AllocatedRefreshToken._MAX_TOKENS_PER_USER[AccessTokenUsage.API]
            == 25
        )

    def test_check_api_refresh_token(self, user: ToolchainUser) -> None:
        now = utcnow()
        customer = Customer.create(slug="kramer", name="Kramerica Industries")
        repo = Repo.create("cookie", customer, "Look to the cookie")
        customer.add_user(user)
        issued_at = now - datetime.timedelta(days=1)
        token_id_1 = AllocatedRefreshToken.allocate_api_token(
            user_api_id=user.api_id,
            issued_at=issued_at,
            expires_at=now - datetime.timedelta(seconds=3),
            description="festivus",
            repo_id="jerry",
            audience=AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.CACHE_RO,
        )
        token_id_2 = AllocatedRefreshToken.allocate_api_token(
            user_api_id=user.api_id,
            issued_at=issued_at,
            expires_at=now + datetime.timedelta(minutes=1),
            description="festivus",
            repo_id="jerry",
            audience=AccessTokenAudience.CACHE_RW | AccessTokenAudience.DEPENDENCY_API,
        )
        token2 = AllocatedRefreshToken.objects.get(id=token_id_2)
        assert token2.last_seen is None
        res, reason = AllocatedRefreshToken.check_api_refresh_token(
            token_id=token_id_1, repo_id=repo.pk, customer_id=customer.pk
        )
        assert res is False
        assert reason == "inactive_token"
        res, reason = AllocatedRefreshToken.check_api_refresh_token(
            token_id=token_id_2, repo_id=repo.pk, customer_id=customer.pk
        )
        assert res is True
        assert reason is None
        token2 = AllocatedRefreshToken.objects.get(id=token_id_2)
        assert token2.last_seen.timestamp() == pytest.approx(now.timestamp())
        assert AllocatedRefreshToken.objects.get(id=token_id_1).last_seen is None

    def test_check_api_refresh_token_revoked_token(self, user: ToolchainUser) -> None:
        customer = Customer.create(slug="kramer", name="Kramerica Industries")
        repo = Repo.create("cookie", customer, "Look to the cookie")
        customer.add_user(user)
        now = utcnow()
        issued_at = now - datetime.timedelta(days=1)
        token_id = AllocatedRefreshToken.allocate_api_token(
            user_api_id=user.api_id,
            issued_at=issued_at,
            expires_at=now + datetime.timedelta(seconds=13),
            description="pole",
            repo_id="jerry",
            audience=AccessTokenAudience.BUILDSENSE_API,
        )
        res, reason = AllocatedRefreshToken.check_api_refresh_token(
            token_id=token_id, repo_id=repo.pk, customer_id=customer.pk
        )
        assert res is True
        assert reason is None
        assert AllocatedRefreshToken.objects.first().revoke() is True
        res, reason = AllocatedRefreshToken.check_api_refresh_token(
            token_id=token_id, repo_id=repo.pk, customer_id=customer.pk
        )
        assert res is False
        assert reason == "inactive_token"

    def test_deactivate_expired_token(self, user: ToolchainUser) -> None:
        now = utcnow()
        customer = Customer.create(slug="kramer", name="Kramerica Industries")
        repo = Repo.create("cookie", customer, "Look to the cookie")
        customer.add_user(user)
        issued_at = now - datetime.timedelta(days=1)
        expired_ids = [
            AllocatedRefreshToken.allocate_api_token(
                user_api_id=user.api_id,
                issued_at=issued_at,
                expires_at=now - datetime.timedelta(seconds=3),
                description="festivus",
                repo_id="jerry",
                audience=AccessTokenAudience.DEPENDENCY_API,
            ),
            AllocatedRefreshToken.allocate_api_token(
                user_api_id=user.api_id,
                issued_at=issued_at,
                expires_at=now - datetime.timedelta(minutes=1),
                description="festivus",
                repo_id="jerry",
                audience=AccessTokenAudience.CACHE_RW,
            ),
            AllocatedRefreshToken.allocate_api_token(
                user_api_id=user.api_id,
                issued_at=issued_at,
                expires_at=now - datetime.timedelta(minutes=10),
                description="festivus",
                repo_id="jerry",
                audience=AccessTokenAudience.CACHE_RW,
            ),
            AllocatedRefreshToken.allocate_api_token(
                user_api_id=user.api_id,
                issued_at=issued_at,
                expires_at=now - datetime.timedelta(hours=1),
                description="festivus",
                repo_id="jerry",
                audience=AccessTokenAudience.CACHE_RW,
            ),
        ]
        valid_ids = [
            AllocatedRefreshToken.allocate_api_token(
                user_api_id=user.api_id,
                issued_at=issued_at,
                expires_at=now + datetime.timedelta(minutes=1),
                description="festivus",
                repo_id="jerry",
                audience=AccessTokenAudience.CACHE_RW,
            ),
            AllocatedRefreshToken.allocate_api_token(
                user_api_id=user.api_id,
                issued_at=issued_at,
                expires_at=now + datetime.timedelta(minutes=2),
                description="festivus",
                repo_id="jerry",
                audience=AccessTokenAudience.CACHE_RW,
            ),
            AllocatedRefreshToken.allocate_api_token(
                user_api_id=user.api_id,
                issued_at=issued_at,
                expires_at=now + datetime.timedelta(hours=3),
                description="festivus",
                repo_id="csomo",
                audience=AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.IMPERSONATE,
            ),
        ]
        assert AllocatedRefreshToken.objects.count() == len(valid_ids + expired_ids) == 7
        for token in AllocatedRefreshToken.objects.all():
            assert token.last_seen is None
            assert token.state == AllocatedRefreshToken.State.ACTIVE
            assert token.usage == AllocatedRefreshToken.Usage.API

        count = AllocatedRefreshToken.deactivate_expired_tokens(now)
        assert count == 4
        for token_id in expired_ids:
            token = AllocatedRefreshToken.objects.get(id=token_id)
            assert token.state == AllocatedRefreshToken.State.EXPIRED
            assert token.last_seen is None
            res, reason = AllocatedRefreshToken.check_api_refresh_token(
                token_id=token_id, repo_id=repo.pk, customer_id=customer.pk
            )
            assert res is False
            assert reason == "inactive_token"
            token = AllocatedRefreshToken.objects.get(id=token_id)
            assert token.last_seen is None
            assert token.state == AllocatedRefreshToken.State.EXPIRED
            assert token.usage == AllocatedRefreshToken.Usage.API

        for token_id in valid_ids:
            token = AllocatedRefreshToken.objects.get(id=token_id)
            assert token.state == AllocatedRefreshToken.State.ACTIVE
            assert token.last_seen is None
            res, reason = AllocatedRefreshToken.check_api_refresh_token(
                token_id=token_id, repo_id=repo.pk, customer_id=customer.pk
            )
            assert res is True
            assert reason is None
            token = AllocatedRefreshToken.objects.get(id=token_id)
            assert token.last_seen.timestamp() == pytest.approx(now.timestamp())
            assert token.state == AllocatedRefreshToken.State.ACTIVE

    def test_check_api_refresh_token_not_existing(self, user: ToolchainUser) -> None:
        now = utcnow()
        issued_at = now - datetime.timedelta(days=1)
        customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer.add_user(user)
        repo = Repo.create("cookie", customer, "Look to the cookie")
        AllocatedRefreshToken.allocate_api_token(
            user_api_id=user.api_id,
            issued_at=issued_at,
            expires_at=now - datetime.timedelta(seconds=3),
            description="pole",
            repo_id="cosmo",
            audience=AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.IMPERSONATE,
        )
        res, reason = AllocatedRefreshToken.check_api_refresh_token(
            token_id="tinsel", repo_id=repo.pk, customer_id=customer.id
        )
        assert res is False
        assert reason == "unknown_token_id"

    def test_check_api_refresh_token_invalid_token_usage(self, user: ToolchainUser) -> None:
        customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer.add_user(user)
        repo = Repo.create("cookie", customer, "Look to the cookie")
        token = AllocatedRefreshToken.get_or_allocate_ui_token(user_api_id=user.api_id, ttl=datetime.timedelta(hours=3))

        res, reason = AllocatedRefreshToken.check_api_refresh_token(
            token_id=token.id, repo_id=repo.pk, customer_id=customer.id
        )
        assert res is False
        assert reason == "invalid_token_usage"

    def test_revoke(self, user: ToolchainUser) -> None:
        now = utcnow()
        issued_at = now - datetime.timedelta(days=1)
        token_id = AllocatedRefreshToken.allocate_api_token(
            user_api_id=user.api_id,
            issued_at=issued_at,
            expires_at=now + datetime.timedelta(seconds=3),
            description="festivus",
            repo_id="george",
            audience=AccessTokenAudience.CACHE_RO | AccessTokenAudience.IMPERSONATE | AccessTokenAudience.CACHE_RW,
        )
        assert AllocatedRefreshToken.objects.count() == 1
        token = AllocatedRefreshToken.objects.first()
        assert token.id == token_id
        assert token.state == AllocatedRefreshToken.State.ACTIVE
        assert token.revoke() is True
        assert AllocatedRefreshToken.objects.count() == 1
        assert token.state == AllocatedRefreshToken.State.REVOKED
        token = AllocatedRefreshToken.objects.first()
        assert token.state == AllocatedRefreshToken.State.REVOKED
        assert token.revoke() is False

    def test_check_refresh_token_invalid_repo(self, user) -> None:
        now = utcnow()
        issued_at = now - datetime.timedelta(days=1)
        customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer.add_user(user)
        Repo.create("cookie", customer, "Look to the cookie")
        token_id = AllocatedRefreshToken.allocate_api_token(
            user_api_id=user.api_id,
            issued_at=issued_at,
            expires_at=now + datetime.timedelta(seconds=13),
            description="festivus",
            repo_id="tinsel",
            audience=AccessTokenAudience.BUILDSENSE_API
            | AccessTokenAudience.IMPERSONATE
            | AccessTokenAudience.CACHE_RW,
        )
        res, reason = AllocatedRefreshToken.check_api_refresh_token(
            token_id=token_id, repo_id="cookie", customer_id=customer.id
        )
        assert res is False
        assert reason == "repo_mismatch"

    def test_check_refresh_token_invalid_customer(self, user) -> None:
        now = utcnow()
        issued_at = now - datetime.timedelta(days=1)
        customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        repo = Repo.create("cookie", customer, "Look to the cookie")
        token_id = AllocatedRefreshToken.allocate_api_token(
            user_api_id=user.api_id,
            issued_at=issued_at,
            expires_at=now + datetime.timedelta(seconds=13),
            description="festivus",
            repo_id="tinsel",
            audience=AccessTokenAudience.BUILDSENSE_API
            | AccessTokenAudience.IMPERSONATE
            | AccessTokenAudience.CACHE_RW,
        )
        res, reason = AllocatedRefreshToken.check_api_refresh_token(
            token_id=token_id, repo_id=repo.pk, customer_id=customer.id
        )
        assert res is False
        assert reason == "customer_mismatch"

    def test_get_active_tokens_for_users_invalid_call(self) -> None:
        with pytest.raises(ToolchainAssertion, match="Empty user API IDs"):
            AllocatedRefreshToken.get_active_tokens_for_users(user_api_ids=[])

    def _get_token_ids(self, tokens: Sequence[AllocatedRefreshToken]) -> set[str]:
        return {token.id for token in tokens}

    def _kill_token(self, token_id: str, state: AccessTokenState = AccessTokenState.EXPIRED) -> None:
        token = AllocatedRefreshToken.objects.get(id=token_id)
        token._token_state = state.value
        token.save()

    @pytest.mark.parametrize("state", [AllocatedRefreshToken.State.EXPIRED, AllocatedRefreshToken.State.REVOKED])
    def test_get_active_tokens_for_users(self, state: AccessTokenState) -> None:
        user_1 = ToolchainUser.create(username="jerry", email="jerry@seinfeld.com")
        user_2 = ToolchainUser.create(username="cosmo", email="cosmo@seinfeld.com")
        user_3 = ToolchainUser.create(username="george", email="george@seinfeld.com")
        user_1_tokens = allocate_fake_api_tokens(user_1, 3)
        user_2_tokens = allocate_fake_api_tokens(user_2, 1)
        user_3_tokens = allocate_fake_api_tokens(user_3, 5)
        active_tokens = AllocatedRefreshToken.get_active_tokens_for_users(user_api_ids=(user_1.api_id, user_2.api_id))
        assert set(user_1_tokens + user_2_tokens) == self._get_token_ids(active_tokens)
        revoked_token = user_1_tokens.pop(1)
        AllocatedRefreshToken.objects.get(id=revoked_token).revoke()
        active_tokens = AllocatedRefreshToken.get_active_tokens_for_users(user_api_ids=(user_1.api_id, user_2.api_id))
        assert set(user_1_tokens + user_2_tokens) == self._get_token_ids(active_tokens)
        self._kill_token(user_2_tokens[0], state=state)
        active_tokens = AllocatedRefreshToken.get_active_tokens_for_users(user_api_ids=(user_1.api_id, user_2.api_id))
        assert set(user_1_tokens) == self._get_token_ids(active_tokens)

        active_tokens = AllocatedRefreshToken.get_active_tokens_for_users(
            user_api_ids=(user_1.api_id, user_2.api_id, user_3.api_id)
        )
        assert set(user_1_tokens + user_3_tokens) == self._get_token_ids(active_tokens)

    def test_get_or_create_refresh_token_for_ui_create(self) -> None:
        assert AllocatedRefreshToken.objects.count() == 0
        now = utcnow()
        token = AllocatedRefreshToken.get_or_allocate_ui_token(user_api_id="mandelbaum", ttl=datetime.timedelta(days=3))
        assert AllocatedRefreshToken.objects.count() == 1
        assert AllocatedRefreshToken.objects.first() == token
        assert token.state == AllocatedRefreshToken.State.ACTIVE
        assert token.usage == AllocatedRefreshToken.Usage.UI
        assert token.issued_at.timestamp() == pytest.approx(now.timestamp())
        assert token.issued_at + datetime.timedelta(days=3) == token.expires_at
        assert token.last_seen is None
        assert isinstance(token.id, str)
        assert len(token.id) == 22

    def test_get_or_create_refresh_token_for_ui_existing(self) -> None:
        now = utcnow()
        yesterday = now - datetime.timedelta(days=1)
        with freeze_time(yesterday):
            existing_token = AllocatedRefreshToken.get_or_allocate_ui_token(
                user_api_id="mandelbaum", ttl=datetime.timedelta(days=10)
            )
        assert AllocatedRefreshToken.objects.count() == 1
        token = AllocatedRefreshToken.get_or_allocate_ui_token(user_api_id="mandelbaum", ttl=datetime.timedelta(days=3))
        assert AllocatedRefreshToken.objects.count() == 1
        assert token.id == existing_token.id
        assert token.state == AllocatedRefreshToken.State.ACTIVE
        assert token.usage == AllocatedRefreshToken.Usage.UI
        assert token.issued_at == existing_token.issued_at == yesterday
        assert token.id == existing_token.id
        assert (
            token.issued_at + datetime.timedelta(days=10) == token.expires_at == yesterday + datetime.timedelta(days=10)
        )

    def test_get_or_create_refresh_token_for_ui_existing_about_to_expire(self) -> None:
        now = utcnow()
        issued_time = now - datetime.timedelta(days=31)
        ttl = datetime.timedelta(days=31) - datetime.timedelta(minutes=4)
        with freeze_time(issued_time):
            existing_token = AllocatedRefreshToken.get_or_allocate_ui_token(user_api_id="mandelbaum", ttl=ttl)
        assert AllocatedRefreshToken.objects.count() == 1
        token = AllocatedRefreshToken.get_or_allocate_ui_token(user_api_id="mandelbaum", ttl=datetime.timedelta(days=3))
        assert existing_token != token
        assert AllocatedRefreshToken.objects.count() == 2
        assert token.issued_at.timestamp() == pytest.approx(now.timestamp())
        assert token.issued_at + datetime.timedelta(days=3) == token.expires_at
        assert token.state == AllocatedRefreshToken.State.ACTIVE
        assert token.usage == AllocatedRefreshToken.Usage.UI

    def test_check_ui_refresh_token(self, user: ToolchainUser) -> None:
        token = AllocatedRefreshToken.get_or_allocate_ui_token(user_api_id=user.api_id, ttl=datetime.timedelta(hours=3))
        res, reason = AllocatedRefreshToken.check_ui_refresh_token(token_id=token.id)
        assert res is True
        assert reason is None

    def test_check_ui_refresh_token_invalid_token_usage(self, user: ToolchainUser) -> None:
        now = utcnow()
        customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer.add_user(user)
        Repo.create("cookie", customer, "Look to the cookie")
        token_id = AllocatedRefreshToken.allocate_api_token(
            user_api_id=user.api_id,
            issued_at=now,
            expires_at=now + datetime.timedelta(days=10),
            description="festivus",
            repo_id="jerry",
            audience=AccessTokenAudience.BUILDSENSE_API,
        )
        res, reason = AllocatedRefreshToken.check_ui_refresh_token(token_id=token_id)
        assert res is False
        assert reason == "invalid_token_usage"

    def test_check_ui_refresh_token_expired_token(self, user: ToolchainUser) -> None:
        issued_at = utcnow() - datetime.timedelta(days=30)
        with freeze_time(issued_at):
            token = AllocatedRefreshToken.get_or_allocate_ui_token(
                user_api_id=user.api_id, ttl=datetime.timedelta(days=26)
            )
            res, reason = AllocatedRefreshToken.check_ui_refresh_token(token_id=token.id)
            assert res is True
        res, reason = AllocatedRefreshToken.check_ui_refresh_token(token_id=token.id)
        assert res is False
        assert reason == "inactive_token"

    def test_check_ui_refresh_token_revoked(self, user: ToolchainUser) -> None:
        token = AllocatedRefreshToken.get_or_allocate_ui_token(user_api_id=user.api_id, ttl=datetime.timedelta(days=26))
        res, reason = AllocatedRefreshToken.check_ui_refresh_token(token_id=token.id)
        assert res is True
        token.revoke()
        res, reason = AllocatedRefreshToken.check_ui_refresh_token(token_id=token.id)
        assert res is False
        assert reason == "inactive_token"

    def test_check_ui_refresh_token_not_existing(self, user: ToolchainUser) -> None:
        token = AllocatedRefreshToken.get_or_allocate_ui_token(user_api_id=user.api_id, ttl=datetime.timedelta(days=26))
        res, reason = AllocatedRefreshToken.check_ui_refresh_token(token_id=token.id[1:])
        assert res is False
        assert reason == "unknown_token_id"

    def test_check_ui_refresh_token_inactive_user(self, user: ToolchainUser) -> None:
        token = AllocatedRefreshToken.get_or_allocate_ui_token(user_api_id=user.api_id, ttl=datetime.timedelta(days=26))
        user.deactivate()
        res, reason = AllocatedRefreshToken.check_ui_refresh_token(token_id=token.id)
        assert res is False
        assert reason == "invalid_user"

    def test_check_ui_refresh_token_invalid_user(self, user: ToolchainUser) -> None:
        token = AllocatedRefreshToken.get_or_allocate_ui_token(
            user_api_id=user.api_id[2:], ttl=datetime.timedelta(days=26)
        )
        res, reason = AllocatedRefreshToken.check_ui_refresh_token(token_id=token.id)
        assert res is False
        assert reason == "invalid_user"

    def _create_token(
        self, user: ToolchainUser, expires_in: datetime.timedelta, last_used_hours_ago: int | None = None
    ):
        now = utcnow()
        token_id = AllocatedRefreshToken.allocate_api_token(
            user_api_id=user.api_id,
            issued_at=datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc),
            expires_at=now + expires_in,
            description="festivus",
            repo_id="jerry",
            audience=AccessTokenAudience.BUILDSENSE_API,
        )
        if last_used_hours_ago:
            token = AllocatedRefreshToken.objects.get(id=token_id)
            token.last_seen = now - datetime.timedelta(hours=last_used_hours_ago)
            token.save()

    def test_get_expiring_api_tokens(self) -> None:
        now = utcnow()
        last_week = now - datetime.timedelta(days=7)
        next_week = now + datetime.timedelta(days=7)
        user_1 = ToolchainUser.create(username="jerry", email="jerry@seinfeld.com")
        user_2 = ToolchainUser.create(username="cosmo", email="cosmo@seinfeld.com")
        user_3 = ToolchainUser.create(username="george", email="george@seinfeld.com")
        allocate_fake_api_tokens(user_1, 3)
        allocate_fake_api_tokens(user_2, 1)
        allocate_fake_api_tokens(user_3, 5)
        assert (
            AllocatedRefreshToken.get_expiring_api_tokens(last_used_threshold=last_week, expiring_on=next_week)
            == tuple()
        )
        self._create_token(user_2, datetime.timedelta(days=3), last_used_hours_ago=10)
        self._create_token(user_1, datetime.timedelta(days=3), last_used_hours_ago=24 * 30)
        tokens = AllocatedRefreshToken.get_expiring_api_tokens(last_used_threshold=last_week, expiring_on=next_week)
        assert len(tokens) == 1
        assert tokens[0].user_api_id == user_2.api_id
        self._create_token(user_1, datetime.timedelta(days=3), last_used_hours_ago=72)
        tokens = AllocatedRefreshToken.get_expiring_api_tokens(last_used_threshold=last_week, expiring_on=next_week)
        assert len(tokens) == 2
        assert {token.user_api_id for token in tokens} == {user_1.api_id, user_2.api_id}

    def _allocate_api_token(self, issued_at, user: ToolchainUser, repo: Repo, desc: str) -> AllocatedRefreshToken:
        token_id = AllocatedRefreshToken.allocate_api_token(
            user_api_id=user.api_id,
            issued_at=issued_at,
            expires_at=issued_at + datetime.timedelta(minutes=14),
            description=desc,
            repo_id=repo.id,
            audience=AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.CACHE_RW,
        )
        return AllocatedRefreshToken.objects.get(id=token_id)

    def test_get_api_tokens_for_user(self, user: ToolchainUser, django_assert_num_queries) -> None:
        def assert_token_repo_1(token):
            assert token.customer_name == "Jerry Seinfeld Inc"
            assert token.customer_slug == "jerry"
            assert token.repo_name == "Look to the cookie"
            assert token.repo_slug == "cookie"

        def assert_token_repo_2(token):
            assert token.customer_name == "Jerry Seinfeld Inc"
            assert token.customer_slug == "jerry"
            assert token.repo_name == "Mail never stops"
            assert token.repo_slug == "mailbox"

        other_user = ToolchainUser.create(username="jerry", email="jerry@seinfeld.com")
        AllocatedRefreshToken.get_or_allocate_ui_token(user_api_id=other_user.api_id, ttl=datetime.timedelta(days=8))
        AllocatedRefreshToken.get_or_allocate_ui_token(
            user_api_id=user.api_id, ttl=datetime.timedelta(days=26)
        ).revoke()
        AllocatedRefreshToken.get_or_allocate_ui_token(user_api_id=user.api_id, ttl=datetime.timedelta(days=10))
        customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        repo_1 = Repo.create("cookie", customer, "Look to the cookie")
        repo_2 = Repo.create("mailbox", customer, "Mail never stops")
        bt = datetime.datetime(2021, 1, 1, tzinfo=datetime.timezone.utc)
        self._allocate_api_token(bt, other_user, repo_1, desc="jerry token")
        self._allocate_api_token(bt + datetime.timedelta(days=9), other_user, repo_2, desc="Jerry, hello")
        assert AllocatedRefreshToken.objects.count() == 5
        with django_assert_num_queries(1):
            tokens = AllocatedRefreshToken.get_api_tokens_for_user(user.api_id)
        assert not tokens
        token_1 = self._allocate_api_token(bt + datetime.timedelta(days=30), user, repo_1, desc="kenny token")
        with django_assert_num_queries(1):
            tokens = AllocatedRefreshToken.get_api_tokens_for_user(user.api_id)
            assert len(tokens) == 1
            assert_token_repo_1(tokens[0])
        token_2 = self._allocate_api_token(bt - datetime.timedelta(days=9), user, repo_1, desc="kramer")
        token_3 = self._allocate_api_token(bt + datetime.timedelta(days=12), user, repo_2, desc="kenny token")
        token_4 = self._allocate_api_token(bt + datetime.timedelta(days=3), user, repo_1, desc="kenny")
        token_1.revoke()
        token_3.last_seen = bt + datetime.timedelta(days=8)
        token_3.save()
        with django_assert_num_queries(1):
            tokens = AllocatedRefreshToken.get_api_tokens_for_user(user.api_id)
            assert len(tokens) == 4
            assert tokens[0].id == token_1.id
            assert tokens[1].id == token_3.id
            assert tokens[2].id == token_4.id
            assert tokens[3].id == token_2.id
            assert_token_repo_1(tokens[0])
            assert_token_repo_1(tokens[3])
            assert_token_repo_1(tokens[2])
            assert_token_repo_2(tokens[1])
            assert tokens[0].last_seen is None
            assert tokens[1].last_seen == datetime.datetime(2021, 1, 9, tzinfo=datetime.timezone.utc)
            assert tokens[2].last_seen is None
            assert tokens[3].last_seen is None

    def test_get_for_user_or_404(self, user: ToolchainUser, django_assert_num_queries) -> None:
        user_2 = ToolchainUser.create(username="cosmo", email="cosmo@seinfeld.com")
        customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        repo = Repo.create("cookie", customer, "Look to the cookie")
        customer.add_user(user)
        customer.add_user(user_2)
        bt = datetime.datetime(2021, 6, 1, tzinfo=datetime.timezone.utc)
        token_1 = self._allocate_api_token(bt, user, repo, desc="jerry token")
        token_2 = self._allocate_api_token(bt + datetime.timedelta(days=9), user_2, repo, desc="k-man")
        with pytest.raises(Http404), django_assert_num_queries(1):
            AllocatedRefreshToken.get_for_user_or_404(token_id="bob", user_api_id=user.api_id)

        with pytest.raises(Http404), django_assert_num_queries(1):
            AllocatedRefreshToken.get_for_user_or_404(token_id=token_2.id, user_api_id=user.api_id)

        with pytest.raises(Http404), django_assert_num_queries(1):
            AllocatedRefreshToken.get_for_user_or_404(token_id=token_1.id, user_api_id=user_2.api_id)
        loaded_token = AllocatedRefreshToken.get_for_user_or_404(token_id=token_2.id, user_api_id=user_2.api_id)
        assert loaded_token.description == "k-man"
        assert loaded_token.id == token_2.id

    def test_set_description(self, user: ToolchainUser) -> None:
        now = utcnow()
        customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        repo = Repo.create("cookie", customer, "Look to the cookie")
        expiration = now + datetime.timedelta(days=10)
        token_id = AllocatedRefreshToken.allocate_api_token(
            user_api_id=user.api_id,
            issued_at=now,
            expires_at=expiration,
            description="festivus",
            repo_id=repo.id,
            audience=AccessTokenAudience.BUILDSENSE_API | AccessTokenAudience.CACHE_RW,
        )
        token = AllocatedRefreshToken.get_for_user_or_404(token_id=token_id, user_api_id=user.api_id)
        assert token.description == "festivus"
        token.set_description("He stopped short?")
        assert token.description == "He stopped short?"
        loaded_token = AllocatedRefreshToken.objects.get(id=token_id)
        assert loaded_token.description == "He stopped short?"

    def test_delete_expired_or_revoked_tokens(self) -> None:
        def get_date(y, m, d) -> datetime.datetime:
            return datetime.datetime(y, m, d, tzinfo=datetime.timezone.utc)

        base_date = get_date(2021, 4, 1)
        user_1 = ToolchainUser.create(username="jerry", email="jerry@seinfeld.com")
        user_2 = ToolchainUser.create(username="cosmo", email="cosmo@seinfeld.com")
        user_1_tokens = allocate_fake_api_tokens(user_1, 3, base_time=base_date)
        user_2_tokens = allocate_fake_api_tokens(user_2, 6, base_time=base_date)
        assert AllocatedRefreshToken.objects.count() == 9
        self._kill_token(user_1_tokens[0])
        self._kill_token(user_2_tokens[-1], state=AllocatedRefreshToken.State.REVOKED)
        assert AllocatedRefreshToken.delete_expired_or_revoked_tokens(get_date(2021, 4, 1)) == 0
        assert AllocatedRefreshToken.objects.count() == 9
        assert AllocatedRefreshToken.delete_expired_or_revoked_tokens(get_date(2021, 4, 15), dry_run=True) == 2
        assert AllocatedRefreshToken.objects.count() == 9
        assert AllocatedRefreshToken.delete_expired_or_revoked_tokens(get_date(2021, 4, 15)) == 2
        assert AllocatedRefreshToken.objects.count() == 7
        assert AllocatedRefreshToken.objects.filter(id__in=[user_1_tokens[0], user_2_tokens[-1]]).count() == 0
