# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum, unique
from functools import reduce
from operator import ior

import shortuuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import models as django_models
from django.db.models import (
    AutoField,
    BooleanField,
    CharField,
    DateTimeField,
    EmailField,
    ForeignKey,
    GenericIPAddressField,
    IntegerField,
    JSONField,
    Q,
    QuerySet,
)

from toolchain.base.datetime_tools import utcnow
from toolchain.base.password import generate_password
from toolchain.base.toolchain_error import ToolchainAssertion, ToolchainError
from toolchain.django.auth.constants import AccessTokenAudience
from toolchain.django.db.base_models import ToolchainModel
from toolchain.django.db.helpers import create_or_update_singleton
from toolchain.django.db.transaction_broker import TransactionBroker
from toolchain.django.site.models import Customer, ToolchainUser
from toolchain.django.util.helpers import get_choices
from toolchain.users.common.constants import AuthProvider
from toolchain.workflow.models import WorkUnitPayload

transaction = TransactionBroker("users")
_logger = logging.getLogger(__name__)


_MAXIMUM_IMPERSONATION_SESSION_LENGTH = timedelta(hours=2)
_IMPERSONATION_LIMIT_SESSIONS_PER_USER = 5
_IMPERSONATION_LIMIT_TIME_SPAN = timedelta(hours=12)
_IMPERSONATION_START_MAX_DELAY = timedelta(minutes=2)


class InvalidAuthUser(ToolchainError):
    pass


class PeriodicallyCheckAccessTokens(WorkUnitPayload):
    # Check access tokens every this many minutes (or None for one-time processing).
    period_minutes = IntegerField(null=True)

    @classmethod
    def create_or_update(cls, period_minutes: int) -> PeriodicallyCheckAccessTokens:
        return create_or_update_singleton(cls, transaction, period_minutes=period_minutes)


class PeriodicallyRevokeTokens(WorkUnitPayload):
    # Revoke active tokens owned by active users.
    period_minutes = IntegerField(null=True)

    # Maximum tokens to revoke in a single run.
    max_tokens = IntegerField(null=False)

    @classmethod
    def create_or_update(cls, period_minutes: int, max_tokens: int | None) -> PeriodicallyRevokeTokens:
        return create_or_update_singleton(cls, transaction, period_minutes=period_minutes, max_tokens=max_tokens)


class PeriodicallyNotifyExpringTokens(WorkUnitPayload):
    # Check access tokens that are about to expire.
    period_minutes = IntegerField(null=True)

    @classmethod
    def create_or_update(cls, period_minutes: int) -> PeriodicallyNotifyExpringTokens:
        return create_or_update_singleton(cls, transaction, period_minutes=period_minutes)


class RestrictedAccessToken(ToolchainModel):
    id = CharField(max_length=22, primary_key=True, default=shortuuid.uuid, editable=False)
    repo_id = CharField(max_length=22, db_index=True, editable=False)
    issued_at = DateTimeField(editable=False, default=utcnow)
    ci_build_key = CharField(max_length=48, db_index=True, editable=False)

    @classmethod
    def allocate(cls, *, key: str, repo_id: str) -> str:
        token = cls.objects.create(repo_id=repo_id, ci_build_key=key)
        return token.id

    @classmethod
    def tokens_for_key(cls, key) -> int:
        return cls.objects.filter(ci_build_key=key).count()


class GithubRepoConfig(ToolchainModel):
    id = AutoField(primary_key=True)
    repo_id = CharField(max_length=22, db_index=True)
    max_build_tokens = IntegerField(default=3)
    started_treshold_sec = IntegerField(default=60 * 6)
    token_ttl_sec = IntegerField(default=60 * 3)

    @classmethod
    def for_repo(cls, repo_id: str) -> GithubRepoConfig | None:
        return cls.get_or_none(repo_id=repo_id)

    @property
    def started_treshold(self) -> datetime.timedelta:
        return datetime.timedelta(seconds=self.started_treshold_sec)

    @property
    def token_ttl(self) -> datetime.timedelta:
        return datetime.timedelta(seconds=self.token_ttl_sec)


class ExchangeCodeState(Enum):
    AVAILABLE = "available"
    EXPIRED = "expired"
    USED = "used"
    OVERRIDDEN = "overridden"


@dataclass(frozen=True)
class ExchangeCodeData:
    user_api_id: str
    repo_id: str
    description: str


class AccessTokenExchangeCode(ToolchainModel):
    EXCHANGE_CODE_TTL = datetime.timedelta(minutes=2)
    State = ExchangeCodeState

    class Meta:
        verbose_name_plural = "JWT Exchange codes"
        verbose_name = "JWT Exchange code"

    user_api_id = CharField(max_length=22, editable=False)
    repo_id = CharField(max_length=22, editable=False)
    created_at = DateTimeField(default=utcnow, editable=False)
    code = CharField(max_length=22, default=shortuuid.uuid, unique=True, editable=False, primary_key=True)
    # _state is used by django internally.
    _code_state = CharField(
        max_length=10,
        default=ExchangeCodeState.AVAILABLE.value,
        db_column="state",
        choices=get_choices(ExchangeCodeState),
    )

    @classmethod
    def create_for_user(cls, user: ToolchainUser, repo_id: str) -> str:
        with transaction.atomic():
            # Scope expiration to client id ? probably not...
            qs = cls.objects.filter(user_api_id=user.api_id, _code_state=ExchangeCodeState.AVAILABLE.value)
            qs.update(_code_state=ExchangeCodeState.OVERRIDDEN.value)
            exchange_code = cls.objects.create(user_api_id=user.api_id, repo_id=repo_id)
            return exchange_code.code

    @classmethod
    def use_code(cls, code: str) -> ExchangeCodeData | None:
        with transaction.atomic():
            exchange_code = cls._get_for_code(code=code)
            if not exchange_code:
                return None
            exchange_code._code_state = ExchangeCodeState.USED.value
            exchange_code.save()
            return ExchangeCodeData(
                user_api_id=exchange_code.user_api_id, repo_id=exchange_code.repo_id, description=str(exchange_code)
            )

    @classmethod
    def _get_for_code(cls, code: str):
        exchange_code = cls.get_or_none(code=code, _code_state=ExchangeCodeState.AVAILABLE.value)
        if not exchange_code:
            _logger.warning(f"No available code for code={code}")
            return None
        expired = exchange_code.expire_if_needed()
        if expired:
            return None
        return exchange_code

    def expire_if_needed(self) -> bool:
        expired = self.created_at + self.EXCHANGE_CODE_TTL < utcnow() and self.is_available
        if not expired:
            return False
        _logger.warning(f"{self} expired")
        self._code_state = ExchangeCodeState.EXPIRED.value
        self.save()
        return True

    @property
    def state(self) -> ExchangeCodeState:
        return ExchangeCodeState(self._code_state)

    @property
    def is_available(self):
        return self.state == ExchangeCodeState.AVAILABLE

    def __str__(self):
        return f"AccessTokenExchangeCode(state={self.state.value} created_at={self.created_at.isoformat()} user_api_id={self.user_api_id} repo_id={self.repo_id})"


@unique
class UserCustomerRole(Enum):
    ORG_ADMIN = "org_admin"
    USER = "user"

    @property
    def is_admin(self) -> bool:
        return self == self.ORG_ADMIN


class OptionalBool(Enum):
    TRUE = "true"
    FALSE = "false"
    UNSET = "unset"

    @classmethod
    def from_bool(cls, value: bool | None) -> OptionalBool:
        if value is None:
            return OptionalBool.UNSET
        return OptionalBool.TRUE if value else OptionalBool.FALSE


class UserCustomerAccessConfig(ToolchainModel):
    Role = UserCustomerRole
    id = AutoField(primary_key=True)
    user_api_id = CharField(max_length=22)
    customer_id = CharField(max_length=22)
    _allowed_audiences = CharField(max_length=250)
    _role = CharField(  # noqa: DJ01
        max_length=15,
        db_column="role",
        editable=True,
        null=True,
        choices=get_choices(UserCustomerRole),
        default=UserCustomerRole.USER.value,
    )

    class Meta:
        unique_together = ("user_api_id", "customer_id")

    @classmethod
    def get_audiences_for_user(cls, *, customer_id: str, user_api_id: str) -> AccessTokenAudience:
        cfg = cls.get_or_none(customer_id=customer_id, user_api_id=user_api_id)
        return cfg.allowed_audiences if cfg else AccessTokenAudience.FRONTEND_API

    @classmethod
    def get_role_for_user(cls, *, customer_id: str, user_api_id: str) -> UserCustomerRole:
        cfg = cls.get_or_none(customer_id=customer_id, user_api_id=user_api_id)
        return cfg.role if cfg else UserCustomerRole.USER

    @classmethod
    def get_role_map_for_user(cls, user_api_id: str) -> dict[str, UserCustomerRole]:
        qs = cls.objects.filter(user_api_id=user_api_id)
        return {uac.customer_id: uac.role for uac in qs}

    @classmethod
    def get_customer_admins(cls, customer: Customer) -> tuple[str, ...]:
        customer_user_api_ids_qs = customer.get_all_active_users_api_ids()
        qs = cls.objects.filter(
            customer_id=customer.id, user_api_id__in=customer_user_api_ids_qs, _role=UserCustomerRole.ORG_ADMIN.value
        )
        return tuple(qs.values_list("user_api_id", flat=True))

    @classmethod
    def create(
        cls,
        *,
        customer_id: str,
        user_api_id: str,
        audience: AccessTokenAudience,
        is_org_admin: bool,
    ) -> UserCustomerAccessConfig:
        role = UserCustomerRole.ORG_ADMIN if is_org_admin else UserCustomerRole.USER
        cfg, created = cls.objects.update_or_create(
            customer_id=customer_id,
            user_api_id=user_api_id,
            defaults={"_allowed_audiences": ",".join(audience.to_claim()), "_role": role.value},
        )
        _logger.info(
            f"UserCustomerAccessConfig.create {user_api_id=} {customer_id=} role={role.value} audience={audience} created={created}"
        )
        if not created:
            cfg.set_admin(is_org_admin)
        return cfg

    @classmethod
    def create_readwrite(
        cls, *, customer_id: str, user_api_id: str, is_org_admin: OptionalBool = OptionalBool.UNSET
    ) -> bool:
        access_config = cls.get_or_none(customer_id=customer_id, user_api_id=user_api_id)
        if access_config:
            if is_org_admin != OptionalBool.UNSET:
                access_config.set_admin(is_admin=is_org_admin == OptionalBool.TRUE)
            return False
        audience = (
            AccessTokenAudience.FRONTEND_API
            | AccessTokenAudience.BUILDSENSE_API
            | AccessTokenAudience.CACHE_RW
            | AccessTokenAudience.CACHE_RO
        )
        if is_org_admin == OptionalBool.TRUE:
            audience |= AccessTokenAudience.IMPERSONATE
        cls.create(
            customer_id=customer_id,
            user_api_id=user_api_id,
            audience=audience,
            is_org_admin=is_org_admin == OptionalBool.TRUE,
        )
        return True

    def set_admin(self, is_admin: bool) -> None:
        role_value = (UserCustomerRole.ORG_ADMIN if is_admin else UserCustomerRole.USER).value
        if role_value == self._role:
            return
        _logger.info(f"set role {self} old={self.role.value} new={role_value}")
        self._role = role_value
        self._set_allow_impersonation(allow_impersonation=is_admin)
        self.save()

    def _set_allow_impersonation(self, allow_impersonation: bool):
        audiences = None
        if not self.allowed_audiences:
            audiences = AccessTokenAudience.IMPERSONATE if allow_impersonation else None
        elif self.allowed_audiences.can_impersonate != allow_impersonation:
            if allow_impersonation:
                _logger.info(f"enable impersonation for {self}")
                audiences = self.allowed_audiences | AccessTokenAudience.IMPERSONATE
            else:
                _logger.info(f"Disable impersonation for {self}")
                audiences = self.allowed_audiences & ~AccessTokenAudience.IMPERSONATE
        if audiences:
            self.set_allowed_audiences(audiences)

    def set_allowed_audiences(self, audiences: AccessTokenAudience) -> None:
        self._allowed_audiences = ",".join(audiences.to_claim())

    @property
    def allowed_audiences(self) -> AccessTokenAudience | None:
        if not self._allowed_audiences:
            return None
        return AccessTokenAudience.from_api_names(self._allowed_audiences.split(","))

    @property
    def role(self) -> UserCustomerRole:
        return UserCustomerRole(self._role) if self._role else UserCustomerRole.USER

    @property
    def is_admin(self) -> bool:
        return self.role.is_admin

    def __str__(self) -> str:
        return f"UserAccess user={self.user_api_id} customer={self.customer_id}"


@dataclass(frozen=True)
class SocialUser:
    # Used to comply with the SocialUser protocol/class expected by social_core.
    uid: str
    provider: str


class UserAuth(ToolchainModel):
    _EMAIL_ADDRS_SEPARATOR = ","
    _MAX_EMAILS = 20
    id = AutoField(primary_key=True)
    user_api_id = CharField(max_length=22, db_index=True)
    _provider = CharField(
        max_length=10, db_index=True, db_column="provider", editable=False, choices=get_choices(AuthProvider)
    )
    user_id = CharField(max_length=48, db_index=True, editable=False)  # user ID in the provider's system
    username = CharField(max_length=150, db_index=True, default="")  # the username on the provider's system.
    created = DateTimeField(editable=False, default=utcnow)
    modified = DateTimeField(auto_now=True)
    _email_addresses = CharField(max_length=256)

    class Meta:
        unique_together = ("user_id", "_provider")

    @classmethod
    def _normalize_emails(cls, emails: Iterable[str]) -> set[str]:
        normalized_emails = {email.lower().strip() for email in emails}
        if "" in normalized_emails:
            normalized_emails.remove("")
        for email in normalized_emails:
            try:
                validate_email(email)
            except ValidationError:
                _logger.warning(f"Invalid email: {email}")
                raise InvalidAuthUser(f"Invald email provided for user {email}")
        if len(normalized_emails) > cls._MAX_EMAILS:
            raise ToolchainAssertion(
                f"Emails address count exceeds max allowed ({cls._MAX_EMAILS}): {normalized_emails=} emails={emails}"
            )
        return normalized_emails

    @classmethod
    def get_by_user_id(cls, provider: AuthProvider, user_id: str) -> UserAuth | None:
        return cls.get_or_none(user_id=user_id, _provider=provider.value)

    @classmethod
    def get_by_username(cls, provider: AuthProvider, username: str) -> UserAuth | None:
        return cls.get_or_none(username=username, _provider=provider.value)

    @classmethod
    def lookup_by_emails(cls, emails: set[str], exclude_provider: AuthProvider) -> tuple[str, ...]:
        normalized_emails = cls._normalize_emails(emails)
        query = reduce(ior, (Q(_email_addresses__contains=email) for email in normalized_emails))
        qs = cls.objects.filter(query).exclude(_provider=exclude_provider.value)
        return tuple(qs.values_list("user_api_id", flat=True).distinct())

    @classmethod
    def get_emails_for_user(cls, user_api_id: str) -> set[str]:
        emails = set()
        for auth in cls.objects.filter(user_api_id=user_api_id):
            emails.update(auth.email_addresses)
        return emails

    @classmethod
    def update_or_create(
        cls, *, user: ToolchainUser, provider: AuthProvider, user_id: str, username: str, emails: Iterable[str]
    ) -> tuple[UserAuth, bool]:
        normalized_emails = cls._normalize_emails(emails)
        emails_list = cls._EMAIL_ADDRS_SEPARATOR.join(sorted(normalized_emails)) if normalized_emails else ""
        auth = cls.get_or_none(user_id=user_id, _provider=provider.value)
        if auth:
            if auth.user_api_id != user.api_id:
                raise InvalidAuthUser(f"{auth} already exists and cannot be associated with {user}")
            if emails_list != auth._email_addresses or username != auth.username:
                auth.username = username
                auth._email_addresses = emails_list
                auth.save()
            return auth, False

        auth = cls.objects.create(
            user_api_id=user.api_id,
            _provider=provider.value,
            user_id=user_id,
            username=username,
            _email_addresses=emails_list,
        )
        _logger.info(f"Created {auth} {user=}")
        return auth, True

    @property
    def provider(self) -> AuthProvider:
        return AuthProvider(self._provider)

    @property
    def email_addresses(self) -> tuple[str, ...]:
        if not self._email_addresses:
            return tuple()
        return tuple(self._email_addresses.split(self._EMAIL_ADDRS_SEPARATOR))

    def get_social_user(self) -> SocialUser:
        return SocialUser(uid=self.user_id, provider=self.provider.value)

    def __str__(self) -> str:
        return f"UserAuth user_api_id={self.user_api_id} {self.user_id}/{self.username}@{self.provider.value}"


def _default_impersonation_session_expires_at():
    return utcnow() + _MAXIMUM_IMPERSONATION_SESSION_LENGTH


class ImpersonationSession(ToolchainModel):
    id = CharField(max_length=22, primary_key=True, default=shortuuid.uuid, editable=False)
    user_api_id = CharField(max_length=22, editable=False)
    impersonator_api_id = CharField(max_length=22, editable=False)
    created_at = DateTimeField(editable=False, default=utcnow)
    expires_at = DateTimeField(editable=False, default=_default_impersonation_session_expires_at)
    started = BooleanField(editable=False, default=False)

    @classmethod
    def create_and_return_id(cls, user_api_id: str, impersonator_api_id: str) -> str:
        if not cls.is_under_impersonation_limit(impersonator_api_id):
            _logger.warning(
                f"User {impersonator_api_id} requested an impersonation session exceeding the 12-hour maximum."
            )
            raise ToolchainError(
                f"User {impersonator_api_id} requested an impersonation session exceeding the 12-hour maximum."
            )

        # Impersonator may only have one session open at once. Close out old sessions.
        cls.invalidate_open_sessions(impersonator_api_id)
        session = cls.objects.create(
            user_api_id=user_api_id,
            impersonator_api_id=impersonator_api_id,
        )
        return session.id

    @classmethod
    def invalidate_open_sessions(cls, impersonator_api_id: str) -> None:
        """Invalidates any open sessions for the given impersonator."""
        cls.objects.filter(
            impersonator_api_id=impersonator_api_id,
            expires_at__gt=utcnow(),
        ).update(expires_at=utcnow())

    @classmethod
    def is_under_impersonation_limit(cls, impersonator_api_id: str) -> bool:
        """Checks whether the given user is under the impersonation limit.

        Currently this is 5 sessions in a 12-hour window.
        """
        session_count = cls.objects.filter(
            impersonator_api_id=impersonator_api_id, created_at__gt=(utcnow() - _IMPERSONATION_LIMIT_TIME_SPAN)
        ).count()

        return session_count < _IMPERSONATION_LIMIT_SESSIONS_PER_USER

    @classmethod
    def get_started_session_for_user_or_none(cls, session_id: str, user_api_id: str) -> ImpersonationSession | None:
        """Returns a session object if it belongs to the given impersonated user, and has been started, otherwise
        None."""

        session = cls.get_or_none(id=session_id)
        if session is None:
            _logger.warning(f"Invalid session id={session_id} was requested.")
            return None

        if session.user_api_id != user_api_id:
            _logger.warning(
                f"Impersonation session {session_id} was requested by user {user_api_id}, but it belongs to {session.user_api_id}."
            )
            return None

        if session.expires_at < utcnow():
            _logger.warning(f"Impersonation session {session_id} was requested after its expiry time.")
            return None
        if not session.started:
            _logger.warning(f"Impersonation session {session.id} was requested, but it hasn't yet started.")
            return None
        return session

    @classmethod
    def get_fresh_session_for_impersonator_or_none(
        cls, session_id: str, impersonator_api_id: str
    ) -> ImpersonationSession | None:
        """Returns a session object if it belongs to the given impersonator, and has not yet been started, otherwise
        None."""

        session = cls.get_or_none(id=session_id)

        if session is None:
            _logger.warning(f"Invalid session id={session_id} was requested.")
            return None

        if session.impersonator_api_id != impersonator_api_id:
            _logger.warning(
                f"Impersonation session {session_id} was requested by user {impersonator_api_id}, but it belongs to {session.impersonator_api_id}."
            )
            return None

        if session.created_at < utcnow() - _IMPERSONATION_START_MAX_DELAY:
            _logger.warning(f"Impersonation session {session_id} wanted to be started too long after its creation.")
            return None

        if session.started:
            _logger.warning(f"Impersonation session {session.id} was requested to start after it had already started.")
            return None
        return session

    def start(self) -> None:
        locked_sessions = ImpersonationSession.objects.filter(id=self.id).select_for_update()
        with transaction.atomic():
            session = locked_sessions.get()
            if session.started:
                _logger.warning(f"Impersonation session {self.id} can't be started because it's already started")
                raise ToolchainAssertion("Cannot start an already started exception")
            session.started = True
            session.save()
        self.refresh_from_db()


class ImpersonationAuditLog(ToolchainModel):
    id = CharField(max_length=22, primary_key=True, default=shortuuid.uuid, editable=False)
    created_at = DateTimeField(editable=False, default=utcnow)
    session_id = ForeignKey(
        ImpersonationSession,
        on_delete=django_models.PROTECT,
        blank=False,
        null=False,
        editable=False,
        db_column="session_id",
    )
    path = CharField(max_length=1024, editable=False)
    method = CharField(max_length=10, editable=False)
    data = JSONField(editable=False, default=dict)

    @classmethod
    def create(cls, session: ImpersonationSession, path: str, method: str, audit_log_data: dict) -> None:
        cls.objects.create(session_id=session, path=path, method=method, data=audit_log_data)


class PeriodicallyExportCustomers(WorkUnitPayload):
    period_minutes = IntegerField(null=True)

    @classmethod
    def create_or_update(cls, period_minutes: int | None) -> PeriodicallyExportCustomers:
        return create_or_update_singleton(cls, transaction, period_minutes=period_minutes)


class UserTermsOfServiceAcceptance(ToolchainModel):
    id = AutoField(primary_key=True, editable=False)
    user_api_id = CharField(max_length=22, db_index=True, editable=False)
    created = DateTimeField(editable=False, default=utcnow)
    tos_version = CharField(max_length=32, db_index=True, editable=False)

    # Extra fields for documentation/audit purposes
    email = EmailField(null=False, editable=False)
    client_ip = GenericIPAddressField(null=False, editable=False)
    request_id = CharField(max_length=40, null=False, editable=False)

    class Meta:
        unique_together = ("user_api_id", "tos_version")

    @classmethod
    def accept_tos(
        cls, *, user_api_id: str, tos_version: str, client_ip: str, user_email: str, request_id: str
    ) -> bool:
        if tos_version != settings.TOS_VERSION:
            # We should never get here, validation logic should be in the caller (api view) code.
            raise ToolchainAssertion("TOS Version mismatch")
        _, created = cls.objects.get_or_create(
            user_api_id=user_api_id,
            tos_version=tos_version,
            defaults={"email": user_email, "client_ip": client_ip, "request_id": request_id},
        )

        return created

    @classmethod
    def has_accepted(cls, user_api_id: str) -> bool:
        return cls.objects.filter(user_api_id=user_api_id, tos_version=settings.TOS_VERSION).exists()


@unique
class RemoteWorkerTokenState(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class RemoteExecWorkerToken(ToolchainModel):
    State = RemoteWorkerTokenState
    id = CharField(max_length=22, primary_key=True, default=shortuuid.uuid, editable=False)
    token = CharField(max_length=64, db_index=True, editable=False, unique=True)
    customer_id = CharField(max_length=22, editable=False, db_index=True)
    created_at = DateTimeField(editable=False, default=utcnow)
    modified_at = DateTimeField(auto_now=True)
    description = CharField(max_length=256)
    # _state is used by django internally.
    _token_state = CharField(
        max_length=10,
        default=RemoteWorkerTokenState.ACTIVE.value,
        db_column="state",
        choices=get_choices(RemoteWorkerTokenState),
    )

    # For auditing purposes.
    user_api_id = CharField(max_length=22, db_index=True, editable=False)

    # For usability in logging/toolshed
    customer_slug = CharField(max_length=64)

    @classmethod
    def create(
        cls, *, customer_id: str, user_api_id: str, customer_slug: str, description: str
    ) -> RemoteExecWorkerToken:
        # TODO: limit number of tokens (active) per customer
        return RemoteExecWorkerToken.objects.create(
            token=generate_password(length=64),
            customer_id=customer_id,
            user_api_id=user_api_id,
            customer_slug=customer_slug,
            description=description,
        )

    @classmethod
    def get_for_customer(cls, *, customer_id) -> tuple[RemoteExecWorkerToken, ...]:
        qs = cls.objects.filter(customer_id=customer_id)
        return tuple(qs.order_by("-created_at"))

    @classmethod
    def get_all_tokens(cls) -> QuerySet:
        return cls.objects.all().order_by("-created_at")

    @classmethod
    def deactivate_or_404(cls, *, customer_id: str, token_id: str) -> RemoteExecWorkerToken:
        token = cls.get_or_404(customer_id=customer_id, id=token_id)
        token.deactivate()
        return token

    @classmethod
    def get_last_change_timestamp(cls) -> datetime.datetime | None:
        rw_token = cls.objects.latest("modified_at")
        return rw_token.modified_at if rw_token else None

    def deactivate(self) -> bool:
        if self.state != RemoteWorkerTokenState.ACTIVE:
            return False
        _logger.info(f"deactivate remote worker token: {self}")
        self._token_state = RemoteWorkerTokenState.INACTIVE.value
        self.save()
        return True

    @property
    def state(self) -> RemoteWorkerTokenState:
        return RemoteWorkerTokenState(self._token_state)

    @property
    def is_active(self) -> bool:
        return self.state == RemoteWorkerTokenState.ACTIVE

    def __str__(self) -> str:
        return f"remote worker token customer={self.customer_slug}/{self.customer_id} created={self.created_at.isoformat()} id={self.id} {self.description}"


class PeriodicallyExportRemoteWorkerTokens(WorkUnitPayload):
    # Export remote worker tokens into a file in s3 so the proxy-server can load them.
    period_seconds = IntegerField(null=True)

    @classmethod
    def create_or_update(cls, period_seconds: int | None) -> PeriodicallyExportRemoteWorkerTokens:
        obj = create_or_update_singleton(cls, transaction, period_seconds=period_seconds)
        _logger.info(obj.description)
        return obj

    def __str__(self) -> str:
        return f"PeriodicallyExportRemoteWorkerTokens - period={self.period_seconds}sec"

    @property
    def description(self) -> str:
        return str(self)
