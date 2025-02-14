# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
import re

import shortuuid
from social_core.exceptions import AuthAlreadyAssociated, AuthForbidden

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.site.auth.toolchain_github import ToolchainGithubOAuth2
from toolchain.django.site.models import Customer, CustomerScmProvider, ToolchainUser
from toolchain.users.models import (
    AuthProvider,
    InvalidAuthUser,
    OptionalBool,
    SocialUser,
    UserAuth,
    UserCustomerAccessConfig,
)

_logger = logging.getLogger(__name__)
_SUPPORTED_PROVIDERS = frozenset(provider.value for provider in AuthProvider)
_BLOCKED_USERNAMES = {"me"}
_MAX_CUSTOMERS_TO_EVALUATE = 3  # Limit the number of customers/gh org we check to prevent us from making to many API calls and increasing latency.
_ACCOUNT_CREATION_THRESHOLD = datetime.timedelta(days=60)


def _check_org_membership(
    *,
    scm_provider: CustomerScmProvider,
    user_handle: str,
    response: dict,
) -> frozenset[Customer]:
    org_names = response["organization_names"]
    scrubbed_response = {key: value for key, value in response.items() if "token" not in key.lower()}
    if not org_names:
        _logger.warning(f"No {scm_provider.value} org names for {user_handle} ({scrubbed_response})")
        return frozenset()
    matched_customers = Customer.for_slugs(org_names, scm=scm_provider)
    _logger.info(f"matched customers for {user_handle}@{scm_provider.value} are: {matched_customers}")
    return matched_customers


def check_is_user_allowed(*, backend, details, response, request, **kwargs) -> None:
    """Checks if a user is allowed to access the toolchain web app.

    We first check of the any of the orgs the user is a member of is a current customer. If there is no match there we
    fall back on checking if the one of the user's emails is in the allow list.
    """
    if backend.name not in _SUPPORTED_PROVIDERS:
        raise AuthForbidden(f"Invalid provider: {backend.name}")
    scm_provider = Customer.Scm(backend.name)
    user_handle = details["username"]
    emails = response.get("verified_emails")
    if not emails:
        _logger.warning(f"No verified emails associated with user {details}")
        raise AuthForbidden("No emails")
    matched_customers = _check_org_membership(
        scm_provider=scm_provider,
        user_handle=user_handle,
        response=response,
    )
    _logger.info(f"is_user_allowed user={user_handle}@{scm_provider.value} matched={matched_customers}")
    response["toolchain_customers"] = matched_customers


def create_user(*, strategy, details, backend, user, response, **kwargs) -> dict:
    if user:
        return {"is_new": False}
    base_username = kwargs.get("username", details["username"])
    primary_email = kwargs.get("email", details["email"])
    account_creation_date = response.get("create_date")
    if not account_creation_date:
        # Soft check for now, make it a hard check later on.
        _logger.warning(f"Missing create_date: {response}")
    full_name = details["fullname"]
    username = _get_username(base_username, backend.name)
    verified_emails = response["verified_emails"]
    if primary_email not in verified_emails:
        verified_emails = {*verified_emails, primary_email}
    selected_email = _get_email(backend, verified_emails)
    toolchain_customers = response["toolchain_customers"]

    customer_slugs = ",".join(customer.slug for customer in toolchain_customers)
    context = f"customer={customer_slugs}" if customer_slugs else ""
    create_active_account = True
    if not customer_slugs and account_creation_date:
        time_since_account_creation = utcnow() - account_creation_date
        create_active_account = time_since_account_creation > _ACCOUNT_CREATION_THRESHOLD
    if not toolchain_customers:
        raise AuthForbidden("No new signups at this time.")
    user = ToolchainUser.create(
        username=username, email=selected_email, full_name=full_name, context=context, is_active=create_active_account
    )
    return {"is_new": True, "user": user}


def _get_username(base_username: str, backend_name: str) -> str:
    is_allowed = base_username.lower() not in _BLOCKED_USERNAMES
    if is_allowed and not ToolchainUser.is_username_exists(base_username):
        return base_username
    uid = shortuuid.uuid()[:5].lower()
    username = f"{base_username}-{backend_name}-{uid}"
    _logger.warning(f"create_user {base_username} already exists, using: {username}")
    return username


INVALID_EMAIL_DOMAIN = "users.noreply.github.com"
PERSONAL_EMAIL_DOMAINS = (
    "gmail.com",
    "outlook.com",
    "hey.com",
    "yahoo.com",
    "live.com",
    "hotmail.com",
    "protonmail.com",
    "fastmail.com",
    "naver.com",  # Korean ISP
)

# People have their .edu email associated w/ the GH account, we want avoid using that email, if possible.
LOW_PRIORTY_DOMAINS = (".edu",)
PERSONAL_EMAIL_DOMAINS_EXP = re.compile("|".join(f".*{dm}" for dm in PERSONAL_EMAIL_DOMAINS))
LOW_PRIORITY_EMAIL_DOMAINS_EXP = re.compile("|".join(f".*{dm}" for dm in LOW_PRIORTY_DOMAINS))


def _get_email_key(email_addr: str) -> tuple[int, str]:
    if PERSONAL_EMAIL_DOMAINS_EXP.match(email_addr.lower()):
        return 100, email_addr
    if LOW_PRIORITY_EMAIL_DOMAINS_EXP.match(email_addr.lower()):
        return 90, email_addr
    return 1, email_addr


def _get_email(backend, verified_emails: set[str]) -> str:
    for email in sorted(verified_emails, key=_get_email_key):
        if email.lower().endswith(INVALID_EMAIL_DOMAIN):
            continue
        if not ToolchainUser.is_email_exists(email):
            return email
    raise AuthAlreadyAssociated(backend, "Email cannot be associated")


def get_org_admins_map(
    backend: ToolchainGithubOAuth2,
    user: ToolchainUser,
    customers: tuple[Customer, ...],
    github_user_id: str,
    access_token: str,
) -> dict[Customer, bool | None]:
    if len(customers) > _MAX_CUSTOMERS_TO_EVALUATE:
        _logger.warning(
            f"too many customers to evaluate for {user} - {len(customers)}. will only evaluate {_MAX_CUSTOMERS_TO_EVALUATE} customers"
        )
        customers = customers[:_MAX_CUSTOMERS_TO_EVALUATE]
    return {customer: backend.is_org_admin(customer.slug, github_user_id, access_token) for customer in customers}


def update_user_details(backend, user, response, details, is_new, **kwargs) -> dict:
    """Social auth pipeline step to create and/or populate UserAuth."""
    if not user or backend.name not in _SUPPORTED_PROVIDERS:
        _logger.warning(f"no user {user}, or unsupported provider: {backend.name=}")
        return {}
    if not user.is_active:
        _logger.warning(f"inactive user {user}")
        return {}
    provider = AuthProvider(backend.name)
    toolchain_customers = response.get("toolchain_customers")
    full_name = details["fullname"]
    _set_user_orgs(allowed_customers=toolchain_customers, user=user)
    user_auth, avatar_url = _create_user_auth(
        backend=backend, details=details, response=response, user=user, provider=provider
    )

    if avatar_url and user.avatar_url != avatar_url:
        # TODO: check allow list for avatar_url domains? otherwise our CSP (CSP_IMG_SRC) settings will block it
        _logger.info(f"update_user_avatar {user} current={user.avatar_url} new={avatar_url}")
        user.avatar_url = avatar_url
        user.save()
    if toolchain_customers:
        _update_access_config(
            backend=backend,
            provider=provider,
            access_token=response["access_token"],
            user=user,
            customers=tuple(toolchain_customers),
            user_auth=user_auth,
        )
    if not is_new and full_name and not user.full_name:
        _logger.info(f"Set full name for {user}: {full_name}")
        user.full_name = full_name
        user.save()
    return {"social": user_auth.get_social_user()}


def _update_access_config(
    *,
    backend,
    provider: AuthProvider,
    access_token: str,
    user: ToolchainUser,
    customers: tuple[Customer, ...],
    user_auth: UserAuth,
) -> None:
    # TODO: we should use bulk action here to avoid multiple DB roundtrips.
    if provider == AuthProvider.GITHUB:
        org_admins_map = get_org_admins_map(
            backend=backend,
            user=user,
            customers=customers,
            github_user_id=user_auth.user_id,
            access_token=access_token,
        )
    else:
        org_admins_map = {}
    for customer in customers:
        is_org_admin = (
            OptionalBool.from_bool(org_admins_map[customer]) if customer in org_admins_map else OptionalBool.UNSET
        )
        UserCustomerAccessConfig.create_readwrite(
            customer_id=customer.id, user_api_id=user.api_id, is_org_admin=is_org_admin
        )


def _create_user_auth(
    *,
    backend,
    details,
    response,
    user: ToolchainUser,
    provider: AuthProvider,
) -> tuple[UserAuth, str]:
    user_handle = details["username"]
    if provider == AuthProvider.GITHUB:
        user_id = str(response["id"])
        avatar_url = response["avatar_url"]
    elif provider == AuthProvider.BITBUCKET:
        user_id = response["account_id"]
        avatar_url = response["links"]["avatar"]["href"]
    else:
        raise ToolchainAssertion("Unsupported auth provider")
    verified_emails: set[str] = set(response.get("verified_emails") or [])
    try:
        user_auth, _ = UserAuth.update_or_create(
            user=user, provider=provider, user_id=user_id, username=user_handle, emails=verified_emails
        )
    except InvalidAuthUser as error:
        _logger.warning(f"update_user_details failed {response}: {error!r}")
        raise AuthAlreadyAssociated(backend, "This account is already in use.")
    return user_auth, avatar_url


def _set_user_orgs(*, allowed_customers: frozenset[Customer], user: ToolchainUser) -> None:
    if not allowed_customers:
        _logger.info(f"associate_user_to_customers {user} clear all customers")
        # user.customeruser_set.clear(bulk=True)
        return
    current_customers_ids = set(user.customers_ids)
    allowed_customers_ids = {cust.id for cust in allowed_customers}
    current_internal_customers = Customer.get_internal_customers_for_ids(current_customers_ids)
    if current_internal_customers:
        _logger.info(f"keeping {user} membership in {current_internal_customers}")
        allowed_customers_ids.update(cust.id for cust in current_internal_customers)
    if current_customers_ids == allowed_customers_ids:  # no-op, most common case.
        return
    user.set_customers(allowed_customers_ids)
    _logger.info(
        f"associate_user_to_customers {user} with {len(allowed_customers)} customers: {allowed_customers} {current_customers_ids=}"
    )


def load_user(backend, details, response, *args, **kwargs) -> dict:
    """basically those functions rolled into one:

    "social_core.pipeline.social_auth.social_uid", "social_core.pipeline.social_auth.auth_allowed",
    "social_core.pipeline.social_auth.social_user", "social_core.pipeline.user.get_username",
    """
    if backend.name not in _SUPPORTED_PROVIDERS:
        return {}
    user_id = backend.get_user_id(details, response)
    if not backend.auth_allowed(response, details):
        raise AuthForbidden(backend)
    provider = AuthProvider(backend.name)
    verified_emails: set[str] = set(response.get("verified_emails") or [])
    user_handle = details["username"]
    social_user, user_api_id = _resolve_user_auth(
        provider=provider, user_id=user_id, verified_emails=verified_emails, user_handle=user_handle
    )
    if user_api_id:
        user = ToolchainUser.get_by_api_id(user_api_id)
        if not user:
            _logger.warning(f"User not found (or not active) for {user_id}/{provider.value} {user_api_id=}")
            raise AuthForbidden(backend)
    else:
        user = None

    data = {
        "uid": user_id,
        # TODO: consider trimming the user name. ToolchainUser.username.max
        "username": details["username"],
        "user": user,
        "social": social_user,
        "is_new": user is None,
        "new_association": social_user is None,
    }
    return data


def _resolve_user_auth(
    provider: AuthProvider, user_id: str, verified_emails: set[str], user_handle: str
) -> tuple[SocialUser | None, str | None]:
    user_auth = UserAuth.get_by_user_id(provider=provider, user_id=user_id)
    if user_auth:
        return user_auth.get_social_user(), user_auth.user_api_id
    if not verified_emails:
        return None, None
    possible_user_api_ids = UserAuth.lookup_by_emails(emails=verified_emails, exclude_provider=provider)
    if len(possible_user_api_ids) != 1:
        _logger.info(
            f"Lookup for existing user {user_handle}/{provider.value} using {verified_emails=} failed. {possible_user_api_ids=}"
        )
        return None, None
    user_api_id = possible_user_api_ids[0]
    _logger.info(f"found existing {user_api_id=} for {user_handle}/{provider.value}")
    return None, user_api_id
