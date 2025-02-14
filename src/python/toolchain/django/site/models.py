# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
from collections.abc import Iterable, Iterator, Sequence
from enum import Enum, unique

import shortuuid
from django.contrib.auth.models import AbstractUser, AnonymousUser
from django.db.models import (
    CASCADE,
    AutoField,
    CharField,
    DateTimeField,
    EmailField,
    ForeignKey,
    ManyToManyField,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    UniqueConstraint,
    URLField,
)
from django.db.models.functions import Lower
from django.http import Http404

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion, ToolchainError
from toolchain.django.auth.constants import AccessTokenAudience
from toolchain.django.db.base_models import ToolchainModel
from toolchain.django.db.transaction_broker import TransactionBroker
from toolchain.django.site.utils.validators import validate_nopipe, validate_noslash
from toolchain.django.util.helpers import get_choices

_logger = logging.getLogger(__name__)
transaction = TransactionBroker("users")


class RepoCreationError(ToolchainError):
    pass


class CustomerSaveError(ToolchainError):
    pass


class ToolchainUser(AbstractUser):
    """A custom user model.

    We need this for two things that the default Django User doesn't support:

    - Enforcing requirement and uniqueness on email addresses.
    - Noting whether an email address is verified.
    """

    class Meta:
        verbose_name_plural = "users"

    id = AutoField(primary_key=True)
    # Override the superclass email field.
    email = EmailField(unique=True, db_index=True)
    full_name = CharField("full name", max_length=150, blank=True, default="")
    modified_at = DateTimeField(auto_now=True)
    # A separate unique ID to avoid using the pk for public-facing services (ie. APIs).
    api_id = CharField(max_length=22, default=shortuuid.uuid, unique=True, db_index=True, editable=False)
    avatar_url = URLField(default="", blank=True)

    @classmethod
    def active_users(cls):
        return cls.objects.filter(is_active=True)

    def deactivate(self):
        self.is_active = False
        self.save()

    @property
    def customers_ids(self) -> list[str]:
        return list(self.customers.values_list("id", flat=True))

    @classmethod
    def is_username_exists(cls, username: str) -> bool:
        return cls.objects.filter(username__iexact=username).exists()

    @classmethod
    def get_user_api_id_for_username(cls, username: str, customer_id: str) -> str | None:
        qs = cls.active_users().filter(username__iexact=username, customeruser__customer_id=customer_id)
        user = qs.first()
        return user.api_id if user else None

    @classmethod
    def is_email_exists(cls, email_addr: str) -> bool:
        return cls.objects.filter(email__iexact=email_addr).exists()

    @classmethod
    def search(cls, term: str) -> list[ToolchainUser]:
        if not term:
            raise ToolchainAssertion(f"search term can't be empty: {term}")
        if "@" in term:
            expression = Q(email__icontains=term)
        else:
            expression = Q(username__icontains=term) | Q(full_name__icontains=term) | Q(api_id=term)
        return list(cls.objects.filter(expression)[:20])

    @classmethod
    def create(
        cls,
        *,
        username: str,
        email: str,
        full_name: str | None = None,
        avatar_url: str | None = None,
        context: str | None = None,
        is_active: bool = True,
    ) -> ToolchainUser:
        user = cls(
            username=username, email=email, full_name=full_name or "", avatar_url=avatar_url or "", is_active=is_active
        )
        user.set_unusable_password()
        user.full_clean()
        user.save()
        _logger.info(
            f"Create new user {username=} {email=} {full_name=} {avatar_url=} id={user.id} api_id={user.api_id} {context or ''} {is_active=}"
        )
        return user

    @classmethod
    def get_inactive_users_api_ids(cls) -> Iterator[str]:
        return cls.objects.filter(is_active=False).values_list("api_id", flat=True).iterator()

    @classmethod
    def get_random(cls) -> ToolchainUser:
        # Not really random right now. since doing order_by("?") is expensive.
        return cls.active_users().order_by("-id").first()

    @classmethod
    def with_api_ids(
        cls, user_api_ids: Sequence[str] | set[str], include_inactive: bool = False
    ) -> Iterator[ToolchainUser]:
        if not user_api_ids:
            raise ToolchainAssertion("user_api_ids is empty")
        qs = cls.objects if include_inactive else cls.active_users()
        qs = qs.filter(api_id__in=user_api_ids)
        return qs.order_by("-id").iterator()

    @classmethod
    def _get_or_none(cls, include_inactive=False, **kwargs):
        qs = cls.objects if include_inactive else cls.active_users()
        try:
            return qs.get(**kwargs)
        except cls.DoesNotExist:
            return None

    @classmethod
    def get_by_api_id(cls, api_id: str, customer_id: str | None = None, include_inactive: bool = False):
        if not customer_id:
            return cls._get_or_none(include_inactive=include_inactive, api_id=api_id)
        return cls._get_or_none(include_inactive=include_inactive, api_id=api_id, customeruser__customer_id=customer_id)

    @classmethod
    def with_user_names(cls, customer_id: str, usernames: set[str]) -> tuple[ToolchainUser, ...]:
        return tuple(CustomerUser.get_users_for_customer(customer_id=customer_id, usernames=usernames))

    @classmethod
    def is_active_and_exists(cls, user_api_id: str) -> bool:
        return cls.active_users().filter(api_id=user_api_id).exists()

    @classmethod
    def get_anonymous_user(cls) -> AnonymousUser:
        return AnonymousUser()

    def is_same_customer_associated(self, other_user_api_id: str, customer_id: str) -> bool:
        if self.api_id == other_user_api_id:
            return True
        return CustomerUser.all_users_belong_to_customer(
            customer_id=customer_id, user_api_ids=(other_user_api_id, self.api_id)
        )

    def get_full_name(self) -> str:
        return self.full_name or self.username

    def set_customers(self, customers_ids: set[str]) -> None:
        def _get_slugs(ids) -> str:
            qs = Customer.objects.filter(id__in=ids)
            return ",".join(qs.values_list("slug", flat=True)) or "NONE"

        with transaction.atomic():
            cs = self.customeruser_set
            curr_assoc = cs.all()
            if customers_ids:
                curr_assoc = curr_assoc.filter(~Q(customer_id__in=customers_ids))
            deleted_assoc_slugs = _get_slugs(curr_assoc.values_list("customer_id", flat=True))
            curr_assoc.delete()
            if customers_ids:
                new_assoc = customers_ids - set(cs.values_list("customer_id", flat=True))
                new_assoc_slugs = _get_slugs(new_assoc)
                cs.add(*(CustomerUser(customer_id=cust_id, user_id=self.id) for cust_id in new_assoc), bulk=False)
            else:
                new_assoc_slugs = "NONE"
        _logger.info(
            f"customers_set_updated user: {self.username}/{self.api_id}: deleted={deleted_assoc_slugs} new={new_assoc_slugs}"
        )

    def save(self, *args, **kwargs):
        if self.is_staff and self.is_active:
            # For now, all staff users are super users (i.e. can do everything in django admin)
            # We might want to reconsider in the future, but for now, this works for us.
            self.is_superuser = True
        else:
            # In all other case (not active or not staff user), disable staff status
            if self.is_superuser:
                logging.info(f"Removing staff status for user {self}")
            self.is_superuser = False
            self.is_staff = False
        return super().save(*args, **kwargs)

    def is_associated_with_active_customers(self) -> bool:
        customer_ids = self.customers_ids
        if not customer_ids:
            return False
        return Customer.active_qs().filter(id__in=customer_ids).exists()


@unique
class CustomerState(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


@unique
class CustomerType(Enum):
    CUSTOMER = "customer"
    INTERNAL = "internal"
    OPEN_SOURCE = "opensource"
    PROSPECT = "prospect"


@unique
class CustomerScmProvider(Enum):
    GITHUB = "github"
    BITBUCKET = "bitbucket"


@unique
class CustomerServiceLevel(Enum):
    FULL_SERVICE = "full_service"
    LIMITED = "limited"


class Customer(ToolchainModel):
    """An organization using toolchain's services."""

    State = CustomerState
    Scm = CustomerScmProvider
    Type = CustomerType
    ServiceLevel = CustomerServiceLevel

    _ALLOWED_CUSTOMER_TYPE_CHANGES = frozenset(
        (
            CustomerType.CUSTOMER,
            CustomerType.PROSPECT,
        )
    )

    # We don't want to use Django's default primary key, which is an autoincrementing integer,
    # as this can expose how many customers we have. Instead we generate a unique id by, e.g.,
    # salting and hashing the name, or some other method TBD, the only restriction being that
    # the id must not contain the slash character '/' or the pipe character '|'.
    id = CharField(max_length=22, primary_key=True, default=shortuuid.uuid, unique=True, db_index=True, editable=False)
    slug = CharField(max_length=64, validators=[validate_noslash, validate_nopipe], unique=True)

    # The short customer name.
    name = CharField(max_length=128, db_index=True)
    created_at = DateTimeField(editable=False, default=utcnow)
    modified_at = DateTimeField(auto_now=True)

    # _state is used by django internally.
    _customer_state = CharField(
        max_length=10, default=CustomerState.ACTIVE.value, db_column="state", choices=get_choices(CustomerState)
    )

    _customer_type = CharField(
        max_length=10, default=CustomerType.PROSPECT.value, db_column="type", choices=get_choices(CustomerType)
    )

    logo_url = URLField(default="", blank=True)
    users = ManyToManyField(ToolchainUser, through="CustomerUser", related_name="customers")
    _scm_provider = CharField(
        max_length=10,
        default=CustomerScmProvider.GITHUB.value,
        db_column="scm_provider",
        verbose_name="SCM Provider",
        choices=get_choices(CustomerScmProvider),
    )
    _service_level = CharField(
        max_length=16,
        default=CustomerServiceLevel.FULL_SERVICE.value,
        db_column="service_level",
        verbose_name="Service Level",
        choices=get_choices(CustomerServiceLevel),
    )

    @classmethod
    def create(
        cls,
        slug: str,
        name: str,
        scm: CustomerScmProvider = CustomerScmProvider.GITHUB,
        customer_type: CustomerType = CustomerType.PROSPECT,
        logo_url: str | None = None,
    ) -> Customer:
        customer = cls.objects.create(
            slug=slug, name=name, _scm_provider=scm.value, _customer_type=customer_type.value, logo_url=logo_url or ""
        )
        customer._log_new_customer()
        return customer

    @classmethod
    def active_qs(cls):
        return cls.objects.filter(_customer_state=CustomerState.ACTIVE.value)

    @classmethod
    def base_qs(cls):
        return cls.active_qs()

    @classmethod
    def for_slugs(cls, slugs: Iterable[str], scm: CustomerScmProvider | None = None) -> frozenset[Customer]:
        """Returns the set of Customers with matching slugs, if any."""
        qs = cls.active_qs().annotate(slug_lower=Lower("slug")).filter(slug_lower__in=(slug.lower() for slug in slugs))
        if scm:
            qs = qs.filter(_scm_provider=scm.value)
        return frozenset(qs)

    @classmethod
    def get_random(cls) -> Customer:
        # Not really random right now. since doing order_by("?") is expensive.
        return cls.active_qs().order_by("-slug").first()

    @classmethod
    def get_internal_customers_for_ids(cls, customer_ids: set[str]) -> tuple[Customer, ...]:
        qs = cls.active_qs().filter(id__in=customer_ids, _customer_type=CustomerType.INTERNAL.value)
        return tuple(qs)

    @classmethod
    def get_for_id_or_none(cls, customer_id: str, include_inactive: bool = False) -> Customer | None:
        if not include_inactive:
            return cls.get_or_none(id=customer_id)
        qs = cls.objects.filter(id=customer_id)
        try:
            return qs.get()
        except cls.DoesNotExist:
            return None

    @classmethod
    def for_slug(cls, slug: str, include_inactive: bool = False) -> Customer | None:
        if include_inactive:
            try:
                return cls.objects.get(slug__iexact=slug)
            except cls.DoesNotExist:
                return None
        return cls.get_or_none(slug__iexact=slug)

    @classmethod
    def for_user_and_slug(cls, *, user_api_id: str, slug: str) -> Customer | None:
        return cls.get_or_none(users__api_id=user_api_id, slug=slug)

    @classmethod
    def exists_user_and_id(cls, *, user_api_id: str, customer_id: str) -> bool:
        return cls.active_qs().filter(users__api_id=user_api_id, id=customer_id).exists()

    @classmethod
    def for_user_and_id(cls, *, user_api_id: str, customer_id: str) -> Customer | None:
        return cls.get_or_none(users__api_id=user_api_id, id=customer_id)

    @classmethod
    def for_api_id(cls, user_api_id: str, user: ToolchainUser):
        # TODO: this API doesn't make a ton of sense.
        # We should get rid of it as we remove the usage of viewsets in users/views_api.py
        customers_ids = user.customers_ids
        return cls.active_qs().filter(users__api_id=user_api_id, id__in=customers_ids)

    @classmethod
    def search(cls, term: str) -> list[Customer]:
        if not term:
            raise ToolchainAssertion(f"search term can't be empty: {term}")
        expression = Q(slug__icontains=term) | Q(name__icontains=term) | Q(id=term)
        return list(cls.objects.filter(expression)[:50])

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"'{self.name}' ({self._customer_type}/{self._scm_provider}) slug={self.slug} id={self.id}"

    def add_user(self, user: ToolchainUser) -> None:
        _logger.info(f"Add {user!r} to {self!r}")
        self.users.add(user)

    @property
    def state(self) -> CustomerState:
        return CustomerState(self._customer_state)

    @property
    def customer_type(self) -> CustomerType:
        return CustomerType(self._customer_type)

    @property
    def is_open_source(self) -> bool:
        return self.customer_type == CustomerType.OPEN_SOURCE

    @property
    def is_internal(self) -> bool:
        return self.customer_type == CustomerType.INTERNAL

    @property
    def scm_provider(self) -> CustomerScmProvider:
        return CustomerScmProvider(self._scm_provider)

    @property
    def service_level(self) -> CustomerServiceLevel:
        return CustomerServiceLevel(self._service_level)

    @property
    def is_limited(self) -> bool:
        return self.service_level == Customer.ServiceLevel.LIMITED

    @property
    def is_in_free_trial(self) -> bool:
        return self.customer_type == CustomerType.PROSPECT

    @property
    def is_active(self) -> bool:
        return self.state == Customer.State.ACTIVE

    def set_service_level(self, service_level: CustomerServiceLevel) -> None:
        if self.service_level == service_level:
            return
        _logger.info(
            f"update_customer: service_level for {self} from {self.service_level.value} to {service_level.value}"
        )
        self._service_level = service_level.value
        self.save()

    def set_type(self, customer_type: CustomerType) -> None:
        if self.customer_type == customer_type:
            return
        if (
            self.customer_type not in self._ALLOWED_CUSTOMER_TYPE_CHANGES
            or customer_type not in self._ALLOWED_CUSTOMER_TYPE_CHANGES
        ):
            raise ToolchainAssertion(f"Not allowed to transition customer of type: {self.customer_type} - {self}")
        _logger.info(f"update_customer: type for {self} from {self.customer_type.value} to {customer_type.value}")
        self._customer_type = customer_type.value
        self.save()

    def deactivate(self) -> bool:
        if not self.is_active:
            return False
        self._customer_state = CustomerState.INACTIVE.value
        self.save()
        return True

    def maybe_set_logo(self, logo_url: str) -> bool:
        if self.logo_url or not logo_url:
            return False
        _logger.info(f"set_logo for customer={self.slug} {logo_url=}")
        self.logo_url = logo_url
        self.save()
        return True

    def set_name(self, new_name: str) -> bool:
        if self.name == new_name:
            return False
        _logger.info(f"update_customer: name {self!r} to {new_name=}")
        self.name = new_name
        self.save()
        return True

    def _log_new_customer(self) -> None:
        _logger.info(f"new_customer_created {self!r}")

    def save(self, *args, **kwargs):
        # This is not an ideal solution, ideally we would also enforce this at the DB level using constraints.
        # However, this is fine for now (May 2022) since the there are two ways to create customers:
        # Toolshed (admin UI) and the GitHub Integration (app_handler.py:_get_customer) which matches customers based on slugs in the first place.
        other = self.for_slug(self.slug)
        is_new = self.id is None
        if not is_new:
            # update
            if other and other.id != self.id:
                raise CustomerSaveError(f"slug '{self.slug}' already used by {other}")
        elif other:
            raise CustomerSaveError(f"slug '{self.slug}' already used by {other}")
        super().save(*args, **kwargs)
        if is_new:
            self._log_new_customer()

    def get_all_active_users_api_ids(self) -> QuerySet:
        qs = CustomerUser.objects.filter(customer_id=self.id, user__is_active=True).select_related("user")
        return qs.values_list("user__api_id", flat=True)


class CustomerUser(ToolchainModel):
    """A many-to-many association between customers and users.

    Having this be many-to-many instead of one-to-many allows us to support a single human user belonging to multiple
    orgs, just as they can on GitHub.

    We use an explicit through table instead of letting Django generate one, so we can add fields to it in the future if
    necessary.
    """

    class Meta:
        verbose_name = "customer-user association"
        verbose_name_plural = "customer-user associations"
        constraints = [UniqueConstraint(fields=["customer", "user"], name="unique_customeruser")]

    id = AutoField(primary_key=True)
    customer = ForeignKey(Customer, on_delete=CASCADE)
    user = ForeignKey(ToolchainUser, on_delete=CASCADE)

    @classmethod
    def get_users_for_customer(cls, customer_id: str, usernames: set[str]) -> Iterable[ToolchainUser]:
        qs = cls.objects.filter(customer_id=customer_id, user__username__in=usernames).select_related("user")
        for cu in qs:
            yield cu.user

    @classmethod
    def get_users_for_customer_by_github_usernames(
        cls, customer_id: str, usernames: set[str]
    ) -> Iterable[ToolchainUser]:
        qs = cls.objects.filter(customer_id=customer_id, user__details__github_username__in=usernames).select_related(
            "user"
        )
        for cu in qs:
            yield cu.user

    @classmethod
    def all_users_belong_to_customer(cls, customer_id: str, user_api_ids: Sequence[str] | set[str]) -> bool:
        qs = cls.objects.filter(
            customer_id=customer_id,
            customer___customer_state=Customer.State.ACTIVE.value,
            user__api_id__in=user_api_ids,
        )
        return qs.count() == len(user_api_ids)


@unique
class RepoState(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


@unique
class RepoVisibility(Enum):
    PUBLIC = "public"
    PRIVATE = "private"


class Repo(ToolchainModel):
    """A code repository we provide services in."""

    MAX_CUSTOMER_REPOS = 25
    State = RepoState
    Visibility = RepoVisibility

    # We don't want to use Django's default primary key, which is an autoincrementing integer,
    # as this can expose how many repos we know about. Instead we generate a unique id by, e.g.,
    # salting and hashing the name, or some other method TBD, the only restriction being that
    # the id must not contain the pipe character '|' or the slash character '/'.
    id = CharField(max_length=22, primary_key=True, default=shortuuid.uuid, unique=True, db_index=True, editable=False)
    slug = CharField(max_length=64, validators=[validate_noslash, validate_nopipe])

    customer = ForeignKey(Customer, on_delete=CASCADE)

    # The short repo name.
    name = CharField(max_length=128, db_index=True)
    created_at = DateTimeField(editable=False, default=utcnow)
    modified_at = DateTimeField(auto_now=True)

    # _state is used by django internally.
    _repo_state = CharField(
        max_length=10, default=RepoState.ACTIVE.value, db_column="state", choices=get_choices(RepoState)
    )

    _visibility = CharField(
        max_length=10, default=RepoVisibility.PRIVATE.value, db_column="visibility", choices=get_choices(RepoVisibility)
    )

    class Meta:
        constraints = [UniqueConstraint(fields=["customer", "slug"], name="unique_customer_repo_slug")]

    def __str__(self) -> str:
        return self.name

    @classmethod
    def allow_repo_activation(cls, customer_id: str) -> bool:
        count = cls._active_qs().filter(customer_id=customer_id).count()
        return count < cls.MAX_CUSTOMER_REPOS

    @classmethod
    def create(cls, slug: str, customer: Customer, name: str) -> Repo:
        repo = cls.get_by_slug_and_customer_id(customer.id, slug=slug)
        if repo:
            return repo
        if not cls.allow_repo_activation(customer_id=customer.id):
            raise RepoCreationError(f"Max number of repos for customer={customer.slug} exceeded.")
        if cls.objects.filter(slug=slug, customer_id=customer.id).exists():
            # This protection is not bulletproof, there is a chance of race conditions. However, at the rate we will be creating repos,
            # the chances of us hitting this race condition is low (and at any case, there is a DB level constraint)
            raise RepoCreationError(f"Repo with {slug=} already exists for {customer}")
        new_repo, _ = cls.objects.get_or_create(slug=slug, customer_id=customer.id, defaults={"name": name})
        return new_repo

    def save(self, force_insert: bool = False, **kwargs):
        super().save(**kwargs)
        if force_insert:
            _logger.info(
                f"repo_created repo_id={self.id} {self.slug=} {self.name=} customer={self.customer.slug} customer_id={self.customer_id}"
            )

    @classmethod
    def _get_by_state(cls, state: RepoState):
        # Advanced Django ORM to ensure a single DB roundtrip when/if repo.customer is accessed.
        return cls.objects.filter(_repo_state=state.value).select_related("customer")

    @classmethod
    def _active_qs(cls):
        return cls._get_by_state(RepoState.ACTIVE)

    @classmethod
    def base_qs(cls):
        return cls._active_qs()

    @classmethod
    def get_inactive(cls):
        return cls._get_by_state(RepoState.INACTIVE)

    @classmethod
    def for_user(cls, user: ToolchainUser):
        # Using some advanced Django ORM to make sure we hit the DB once.
        sq = Subquery(CustomerUser.objects.filter(user_id=user.id).values("customer_id"))
        return cls._active_qs().filter(customer_id__in=sq).order_by("slug")

    @classmethod
    def get_for_slugs_or_none(
        cls, *, customer_slug: str, repo_slug: str, include_inactive: bool = False
    ) -> Repo | None:
        if not include_inactive:
            return cls.get_or_none(
                slug=repo_slug, customer__slug=customer_slug, customer___customer_state=CustomerState.ACTIVE.value
            )
        # This will raise a DoesNotExist exception if those can't be found, which is fine for this use case.
        return cls.objects.get(slug=repo_slug, customer__slug=customer_slug)

    @classmethod
    def for_customer(cls, customer: Customer):
        return cls.for_customer_id(customer.id) if customer else cls.objects.none()

    @classmethod
    def for_customer_id(cls, customer_id: str, include_inactive: bool = False):
        base_qs = cls.objects if include_inactive else cls._active_qs()
        # active repos first, then order by slug
        return base_qs.filter(customer_id=customer_id).order_by("_repo_state", "slug")

    @classmethod
    def get_by_slug_and_customer_id(cls, customer_id: str, slug: str, include_inactive: bool = False) -> Repo | None:
        base_qs = cls.objects if include_inactive else cls._active_qs()
        qs = base_qs.filter(customer_id=customer_id, slug=slug)
        try:
            return qs.get()
        except cls.DoesNotExist:
            return None

    @classmethod
    def get_for_id_and_user_or_none(cls, repo_id: str, user: ToolchainUser):
        # TODO: Scoping to repos owned by the user should be done in the lower layer somehow.
        # i.e. some kind of thing that adds this condition to every query (on the connection level)
        return cls.get_or_none(id=repo_id, customer_id__in=user.customers_ids)

    @classmethod
    def get_for_id_or_none(cls, repo_id: str, include_inactive: bool = False):
        qs = (
            cls.objects.filter(id=repo_id).select_related("customer")
            if include_inactive
            else cls._active_qs().filter(id=repo_id)
        )
        try:
            return qs.get()
        except cls.DoesNotExist:
            return None

    @classmethod
    def get_or_none_for_slug(cls, slug: str, user: ToolchainUser):
        return cls.get_or_none(customer_id__in=user.customers_ids, slug=slug)

    @classmethod
    def get_or_none_for_slugs_and_user(cls, *, repo_slug: str, customer_slug: str, user: ToolchainUser):
        return cls.get_or_none(
            customer_id__in=user.customers_ids,
            slug=repo_slug,
            customer__slug=customer_slug,
            customer___customer_state=CustomerState.ACTIVE.value,
        )

    @classmethod
    def get_or_404_for_slugs_and_user(cls, *, repo_slug: str, customer_slug: str, user: ToolchainUser):
        repo = cls.get_or_none_for_slugs_and_user(repo_slug=repo_slug, customer_slug=customer_slug, user=user)
        if not repo:
            _logger.warning(f"Repo not found with {repo_slug=} {customer_slug=} {user=}")
            raise Http404("No Repo matches the given query.")
        return repo

    @classmethod
    def with_api_ids(cls, repo_ids: Sequence[str] | set[str], customer_id: str | None = None) -> tuple[Repo, ...]:
        if not repo_ids:
            raise ToolchainAssertion("repo_ids is empty")
        qs = cls.for_customer_id(customer_id) if customer_id else cls._active_qs()
        return tuple(qs.filter(id__in=repo_ids))

    @classmethod
    def get_by_id_or_404(cls, customer_id: str, repo_id: str) -> Repo:
        return cls.get_or_404(id=repo_id, customer_id=customer_id)

    @classmethod
    def get_by_ids_and_user_or_404(cls, customer_id: str, repo_id: str, user: ToolchainUser) -> Repo:
        return cls.get_or_404(
            id=repo_id,
            customer_id=customer_id,
            customer___customer_state=CustomerState.ACTIVE.value,
            customer_id__in=user.customers_ids,
        )

    @classmethod
    def exists_for_customer(cls, repo_id: str, customer_id: str) -> bool:
        return cls._active_qs().filter(id=repo_id, customer_id=customer_id).exists()

    @classmethod
    def exists(cls, repo_id: str, user: ToolchainUser):
        return cls._active_qs().filter(id=repo_id, customer_id__in=user.customers_ids).exists()

    @classmethod
    def get_random(cls):
        # Not really random right now. since doing order_by("?") is expensive.
        return cls._active_qs().order_by("-id").first()

    @property
    def state(self) -> RepoState:
        return RepoState(self._repo_state)

    @property
    def visibility(self) -> RepoVisibility:
        return RepoVisibility(self._visibility)

    @property
    def is_active(self) -> bool:
        return self.state == RepoState.ACTIVE

    @property
    def full_name(self) -> str:
        return f"{self.customer.slug}/{self.slug}"

    def deactivate(self) -> None:
        _logger.info(
            f"deactivate_repo repo_id={self.id} slug={self.slug} customer={self.customer.slug} state={self.state.value}"
        )
        self._repo_state = RepoState.INACTIVE.value
        self.save()

    def activate(self) -> None:
        _logger.info(
            f"activate_repo repo_id={self.id} slug={self.slug} customer={self.customer.slug} state={self.state.value}"
        )
        self._repo_state = RepoState.ACTIVE.value
        self.save()


class MaxActiveTokensReachedError(ToolchainError):
    pass


@unique
class AccessTokenState(Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


@unique
class AccessTokenUsage(Enum):
    API = "api"
    UI = "ui"


class AllocatedRefreshToken(ToolchainModel):
    _MAX_TOKENS_PER_USER = {AccessTokenUsage.API: 25, AccessTokenUsage.UI: 5}
    State = AccessTokenState
    Usage = AccessTokenUsage

    class Meta:
        db_table = "site_allocatedaccesstoken"

    id = CharField(max_length=22, primary_key=True, default=shortuuid.uuid, editable=False)
    user_api_id = CharField(max_length=22, db_index=True, editable=False)
    expires_at = DateTimeField(editable=False, db_index=True)
    _token_state = CharField(
        max_length=10,
        default=AccessTokenState.ACTIVE.value,
        db_index=True,
        null=False,
        db_column="token_state",
        choices=get_choices(AccessTokenState),
    )
    issued_at = DateTimeField(editable=False)
    last_seen = DateTimeField(null=True)
    _usage = CharField(
        max_length=6,
        default=AccessTokenUsage.API.value,
        null=False,
        db_column="usage",
        choices=get_choices(AccessTokenUsage),
        editable=False,
    )
    # These fields are for meta data management/visibility purposes and are not current required or checked/enforced.
    description = CharField(max_length=256, default="NA")
    repo_id = CharField(max_length=22, default="", null=True, editable=False)  # noqa: DJ01
    _audiences = CharField(max_length=250, db_column="audiences", default="", null=True, editable=False)  # noqa: DJ01

    @property
    def state(self) -> AccessTokenState:
        return AccessTokenState(self._token_state)

    @property
    def usage(self) -> AccessTokenUsage:
        return AccessTokenUsage(self._usage)

    @property
    def audiences(self) -> AccessTokenAudience | None:
        if not self._audiences:
            return None
        return AccessTokenAudience.from_api_names(self._audiences.split(","))

    @property
    def is_active(self) -> bool:
        return self.state == AccessTokenState.ACTIVE

    def revoke(self) -> bool:
        if not self.is_active:
            return False
        _logger.info(f"revoke_token id={self.id} state={self._token_state}")
        self._token_state = AccessTokenState.REVOKED.value
        self.save()
        return True

    def set_description(self, desc: str) -> None:
        _logger.info(f"set_description id={self.id} old={self.description} new={desc}")
        self.description = desc
        self.save()

    @classmethod
    def get_max_api_tokens(cls) -> int:
        return cls._MAX_TOKENS_PER_USER[AccessTokenUsage.API]

    @classmethod
    def _user_active_tokens(
        cls,
        user_api_id: str,
        expiration_threshold: datetime.datetime | None = None,
        usage: AccessTokenUsage | None = None,
    ) -> QuerySet:
        qs = cls.objects.filter(user_api_id=user_api_id, _token_state=AccessTokenState.ACTIVE.value)
        if expiration_threshold:
            qs = qs.filter(expires_at__gt=expiration_threshold)
        if usage:
            qs = qs.filter(_usage=usage.value)
        return qs

    @classmethod
    def get_active_tokens_for_users(cls, user_api_ids: Sequence[str]) -> tuple[AllocatedRefreshToken, ...]:
        if not user_api_ids:
            raise ToolchainAssertion("Empty user API IDs")
        qs = cls.objects.filter(_token_state=AccessTokenState.ACTIVE.value, user_api_id__in=user_api_ids)
        return tuple(qs)

    @classmethod
    def get_expiring_api_tokens(
        cls, *, last_used_threshold: datetime.datetime, expiring_on: datetime.datetime
    ) -> tuple[AllocatedRefreshToken, ...]:
        qs = cls.objects.filter(
            _token_state=AccessTokenState.ACTIVE.value,
            _usage=AccessTokenUsage.API.value,
            last_seen__gte=last_used_threshold,
            expires_at__lte=expiring_on,
        )
        return tuple(qs)

    @classmethod
    def deactivate_expired_tokens(cls, expiration_threshold: datetime.datetime) -> int:
        """Changes the state of expired active token to expired.

        Returns the number of token that have been deactivated
        """
        qs = cls.objects.filter(_token_state=AccessTokenState.ACTIVE.value, expires_at__lt=expiration_threshold)
        return qs.update(_token_state=AccessTokenState.EXPIRED.value)

    @classmethod
    def get_expired_or_revoked_tokens(cls, expiration_deletetion_threshold: datetime.datetime) -> QuerySet:
        return cls.objects.filter(
            _token_state__in=(AccessTokenState.EXPIRED.value, AccessTokenState.REVOKED.value),
            expires_at__lt=expiration_deletetion_threshold,
        )

    @classmethod
    def delete_expired_or_revoked_tokens(
        cls, expiration_deletetion_threshold: datetime.datetime, dry_run: bool = False
    ) -> int:
        qs = cls.get_expired_or_revoked_tokens(expiration_deletetion_threshold)
        if dry_run:
            return qs.count()
        deleted_count, _ = qs.delete()
        return deleted_count

    @classmethod
    def _check_token(
        cls, *, token_id: str, now: datetime.datetime, usage: AccessTokenUsage
    ) -> tuple[AllocatedRefreshToken | None, str | None]:
        token = cls.get_or_none(id=token_id)
        if not token:
            return None, "unknown_token_id"
        if token.usage != usage:
            return None, "invalid_token_usage"

        is_active = token.state == AccessTokenState.ACTIVE and token.expires_at > now
        if not is_active:
            return None, "inactive_token"
        return token, None

    @classmethod
    def check_ui_refresh_token(cls, *, token_id: str) -> tuple[bool, str | None]:
        now = utcnow()
        token, reason = cls._check_token(token_id=token_id, now=now, usage=AccessTokenUsage.UI)
        if not token:
            return False, reason
        if not ToolchainUser.is_active_and_exists(token.user_api_id):
            return False, "invalid_user"
        token.last_seen = now
        token.save()
        return True, None

    @classmethod
    def check_api_refresh_token(cls, *, token_id: str, repo_id: str, customer_id: str) -> tuple[bool, str | None]:
        now = utcnow()
        token, reason = cls._check_token(token_id=token_id, now=now, usage=AccessTokenUsage.API)
        if not token:
            return False, reason
        if not Repo.exists_for_customer(repo_id=repo_id, customer_id=customer_id):
            return False, "repo_mismatch"
        if not Customer.exists_user_and_id(user_api_id=token.user_api_id, customer_id=customer_id):
            return False, "customer_mismatch"

        token.last_seen = now
        token.save()
        return True, None

    @classmethod
    def allocate_api_token(
        cls,
        *,
        user_api_id: str,
        issued_at: datetime.datetime,
        expires_at: datetime.datetime,
        description: str,
        repo_id: str,
        audience: AccessTokenAudience,
    ) -> str:
        return cls._allocate(
            user_api_id=user_api_id,
            issued_at=issued_at,
            expires_at=expires_at,
            usage=AccessTokenUsage.API,
            description=description,
            repo_id=repo_id,
            audience=audience,
        ).id

    @classmethod
    def get_or_allocate_ui_token(cls, *, user_api_id: str, ttl: datetime.timedelta) -> AllocatedRefreshToken:
        now = utcnow()
        expiration_threshold = now + datetime.timedelta(minutes=10)
        tokens_qs = cls._user_active_tokens(
            user_api_id=user_api_id, expiration_threshold=expiration_threshold, usage=AccessTokenUsage.UI
        )
        token = tokens_qs.first()
        if token:
            return token
        return cls._allocate(
            user_api_id=user_api_id,
            issued_at=now,
            expires_at=now + ttl,
            usage=AccessTokenUsage.UI,
            active_tokens=tokens_qs,
            description="",
        )

    @classmethod
    def has_reached_max_api_tokens(cls, user_api_id: str) -> bool:
        max_reached, _ = cls._has_reached_max_tokens(
            user_api_id=user_api_id, expiration_threshold=utcnow(), usage=AccessTokenUsage.API
        )
        return max_reached

    @classmethod
    def _has_reached_max_tokens(
        cls,
        user_api_id: str,
        expiration_threshold: datetime.datetime,
        usage: AccessTokenUsage,
        active_tokens: QuerySet | None = None,
    ) -> tuple[bool, int]:
        if active_tokens is None:
            active_tokens = cls._user_active_tokens(
                user_api_id=user_api_id, expiration_threshold=expiration_threshold, usage=usage
            )
        active_tokens_count = active_tokens.count()
        return active_tokens_count >= cls._MAX_TOKENS_PER_USER[usage], active_tokens_count

    @classmethod
    def _allocate(
        cls,
        *,
        user_api_id: str,
        issued_at: datetime.datetime,
        expires_at: datetime.datetime,
        usage: AccessTokenUsage,
        description: str,
        active_tokens: QuerySet | None = None,
        repo_id: str | None = None,
        audience: AccessTokenAudience | None = None,
    ) -> AllocatedRefreshToken:
        max_reached, active_tokens_count = cls._has_reached_max_tokens(
            user_api_id=user_api_id, expiration_threshold=issued_at, usage=usage, active_tokens=active_tokens
        )
        if max_reached:
            raise MaxActiveTokensReachedError(
                f"Max number of active tokens reached. active_tokens={active_tokens_count}"
            )
        token = cls.objects.create(
            user_api_id=user_api_id,
            issued_at=issued_at,
            expires_at=expires_at,
            _usage=usage.value,
            description=description,
            repo_id=repo_id,
            _audiences=",".join(audience.to_claim()) if audience else None,
        )
        _logger.info(
            f"Allocated refresh_token token.id={token.id} {active_tokens_count=} usage={usage.value} {user_api_id=}"
        )
        return token

    @classmethod
    def _add_annotations(cls, queryset):
        repo_ref = Repo.objects.filter(id=OuterRef("repo_id"))
        qs = queryset.annotate(
            repo_name=Subquery(repo_ref.values("name")),
            repo_slug=Subquery(repo_ref.values("slug")),
            customer_id=Subquery(repo_ref.values("customer_id")),
        )
        customer_ref = Customer.objects.filter(id=OuterRef("customer_id"))
        qs = qs.annotate(
            customer_name=Subquery(customer_ref.values("name")), customer_slug=Subquery(customer_ref.values("slug"))
        )
        return qs

    @classmethod
    def get_api_tokens_for_user(cls, user_api_id: str):
        # Annotate w/ repo & customer data
        qs = cls.objects.filter(user_api_id=user_api_id, _usage=AccessTokenUsage.API.value)
        qs = cls._add_annotations(qs)
        return list(qs.order_by("-issued_at", "-expires_at"))

    @classmethod
    def get_for_user_or_404(cls, token_id: str, user_api_id: str) -> AllocatedRefreshToken:
        return cls.get_or_404(id=token_id, user_api_id=user_api_id)


_MODELS_TO_CHECK = [ToolchainUser, Repo, Customer]


def check_models_read_access():
    data = {model.__name__: model.get_random().pk for model in _MODELS_TO_CHECK}
    return data
