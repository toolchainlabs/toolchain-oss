# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from typing import cast

from django.conf import settings
from django.http import HttpResponseBadRequest
from jose import jwt
from prometheus_client import Counter, Histogram

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion, ToolchainError
from toolchain.django.auth.claims import Claims, RepoClaims, UserClaims
from toolchain.django.auth.constants import AccessTokenAudience, AccessTokenType
from toolchain.django.site.models import (
    AllocatedRefreshToken,
    Customer,
    MaxActiveTokensReachedError,
    Repo,
    ToolchainUser,
)
from toolchain.users.jwt.constants import UI_REFRESH_TOKEN_TTL
from toolchain.users.jwt.encoder import JWTEncoder
from toolchain.users.jwt.keys import JWTSecretData, JWTSecretKey

_logger = logging.getLogger(__name__)


ACCESS_TOKEN_CHECK = Counter(
    name="toolchain_access_tokens_check", documentation="Count access token checks.", labelnames=["token_type"]
)


ACCESS_TOKEN_CHECK_FAILURE = Counter(
    name="toolchain_access_tokens_check_failure",
    documentation="Count access token check failures labelled by error (exception) type.",
    labelnames=["error_type", "token_type", "customer", "token_id"],
)


ACCESS_TOKEN_TIME_LEFT = Histogram(
    name="toolchain_access_tokens_time_left",
    documentation="Time left before token expiration",
    labelnames=["api"],
    buckets=(10, 40, 60, 180, 300, 480, 600, 900, 1200, 2000, 2700, 4500, float("inf")),
)

LOW_EXPIRATION_THRESHOLD_SECONDS = 15
MAX_TTL_FOR_DB_CHECK_BYPASS = datetime.timedelta(minutes=25)


@dataclass(frozen=True)
class AccessToken:
    token: str
    expiration: datetime.datetime


class InvalidAccessTokenError(ToolchainError):
    def __init__(
        self,
        *,
        msg,
        reason: str,
        token_type: AccessTokenType | None,
        error: Exception | None = None,
        token_id: str | None = None,
        customer_id: str | None = None,
    ) -> None:
        super().__init__(msg)
        self._reason = reason or "na"
        self._root_error = error
        self._token_type = token_type.value if token_type else "NA"
        self._token_id = token_id or "NA"
        self._customer_id = customer_id or "NA"

    @property
    def reason(self) -> str:
        return self._reason

    @property
    def token_type(self) -> str:
        return self._token_type

    def get_message(self) -> str:
        root_error = f" - {self._root_error!r}" if self._root_error else ""
        return f"{self}{root_error}"

    @property
    def token_id(self) -> str:
        return self._token_id

    @property
    def customer_id(self) -> str:
        return self._customer_id


class InvalidTokenRequest(ToolchainError):
    def __init__(self, msg, status_code=HttpResponseBadRequest.status_code):
        super().__init__(msg)
        self.status_code = status_code
        self.msg = msg


def generate_refresh_token(
    *,
    user: ToolchainUser,
    repo_pk: str,
    customer: Customer,
    expiration_time: datetime.datetime,
    audience: AccessTokenAudience,
    description: str,
) -> str:
    # See https://tools.ietf.org/html/rfc7519#section-4.1 for Registered Claim Names
    if not audience:
        raise ToolchainAssertion("Must specify audience.")
    now = utcnow()
    try:
        token_id = AllocatedRefreshToken.allocate_api_token(
            user_api_id=user.api_id,
            issued_at=now,
            expires_at=expiration_time,
            description=description,
            repo_id=repo_pk,
            audience=audience,
        )
    except MaxActiveTokensReachedError:
        _logger.warning(f"Max number of active tokens reached for {user}.", exc_info=True)
        raise InvalidTokenRequest("Max number of active tokens reached", status_code=401)
    encoder = JWTEncoder(settings.JWT_AUTH_KEY_DATA)
    token_str = encoder.encode_refresh_token(
        token_id=token_id,
        expires_at=expiration_time,
        issued_at=now,
        audience=audience,
        username=user.username,
        user_api_id=user.api_id,
        repo_id=repo_pk,
        customer_id=customer.pk,
    )
    _logger.info(
        f"generate_token type=refresh_api username={user.username} customer={customer.slug} repo={repo_pk} expires_at={expiration_time.isoformat()}"
    )
    return token_str


def get_or_create_refresh_token_for_ui(
    user: ToolchainUser, impersonation_session_id: str | None = None
) -> tuple[str, datetime.datetime]:
    token = AllocatedRefreshToken.get_or_allocate_ui_token(user_api_id=user.api_id, ttl=UI_REFRESH_TOKEN_TTL)
    expires_at = token.expires_at
    encoder = JWTEncoder(settings.JWT_AUTH_KEY_DATA)
    token_str = encoder.encode_refresh_token(
        token_id=token.id,
        expires_at=expires_at,
        issued_at=token.issued_at,
        audience=AccessTokenAudience.FRONTEND_API,
        username=user.username,
        user_api_id=user.api_id,
        impersonation_session_id=impersonation_session_id,
    )
    _logger.info(f"generate_token type=refresh_ui username={user.username} expires_at={expires_at.isoformat()}")
    return token_str, expires_at


def _get_claims(
    claims_dict: dict, audience: AccessTokenAudience, impersonation_user_api_id: str | None = None
) -> tuple[Claims, bool]:
    is_ui_token = audience == AccessTokenAudience.FRONTEND_API
    if is_ui_token:
        if impersonation_user_api_id:
            raise InvalidAccessTokenError(
                msg="Impersonation not supported for UI tokens.",
                reason="impersonation_not_allowed",
                token_type=AccessTokenType.REFRESH_TOKEN,
                # token_id=claims_dict,
            )
        claims = cast(Claims, UserClaims.create_user_claims(claims_dict, audience))
    else:
        claims = cast(Claims, RepoClaims.create_repo_claims(claims_dict, audience, impersonation_user_api_id))
    return claims, is_ui_token


def check_refresh_token(token_str: str) -> Claims:
    ACCESS_TOKEN_CHECK.labels(token_type=AccessTokenType.REFRESH_TOKEN.value).inc()
    try:
        claims_dict, audience = _decode_jwt(token_str, AccessTokenType.REFRESH_TOKEN)
        bypass_db_check = claims_dict.pop("bypass_db", False)
        claims, is_ui_token = _get_claims(claims_dict, audience)
        if claims.token_type != AccessTokenType.REFRESH_TOKEN:
            raise InvalidAccessTokenError(
                msg="Invalid token type.", reason="InvalidType", token_type=AccessTokenType.REFRESH_TOKEN
            )

        if bypass_db_check:
            _check_refresh_token_bypass(claims, claims_dict)
        else:
            _check_refresh_token_db(claims=claims, is_ui_token=is_ui_token)

    except InvalidAccessTokenError as error:
        _report_token_check_failure(error)
        raise
    return claims


def _check_refresh_token_db(claims: Claims, is_ui_token: bool) -> None:
    token_id = cast(str, claims.token_id)
    if is_ui_token:
        token_valid, reason = AllocatedRefreshToken.check_ui_refresh_token(token_id=token_id)
        if token_valid:
            return
        raise InvalidAccessTokenError(
            msg=f"Unknown UI token with id={token_id}",
            reason=reason,  # type: ignore[arg-type]
            token_type=AccessTokenType.REFRESH_TOKEN,
            token_id=token_id,
        )

    repo_claims = cast(RepoClaims, claims)
    token_valid, reason = AllocatedRefreshToken.check_api_refresh_token(
        token_id=token_id, repo_id=repo_claims.repo_pk, customer_id=repo_claims.customer_pk
    )
    if not token_valid:
        raise InvalidAccessTokenError(
            msg=f"Unknown API token with id={token_id}",
            reason=reason,  # type: ignore[arg-type]
            token_type=AccessTokenType.REFRESH_TOKEN,
            token_id=token_id,
            customer_id=repo_claims.customer_pk,
        )


def _check_refresh_token_bypass(claims: Claims, claims_dict: dict):
    max_expiration = (utcnow() + MAX_TTL_FOR_DB_CHECK_BYPASS).timestamp()
    expiration_ts = claims_dict["exp"]

    if expiration_ts > max_expiration:
        raise InvalidAccessTokenError(
            msg=f"Invalid expiration {expiration_ts}", reason="invalid_bypass_expiration", token_type=AccessTokenType.REFRESH_TOKEN  # type: ignore[arg-type]
        )
    user = ToolchainUser.get_by_api_id(api_id=claims.user_api_id, include_inactive=False)
    if not user or user.username != claims.username:
        raise InvalidAccessTokenError(
            msg=f"Invalid/inactive user specified {claims.user_api_id}/{claims.username} {user=}", reason="invalid_bypass_user", token_type=AccessTokenType.REFRESH_TOKEN  # type: ignore[arg-type]
        )
    if not isinstance(claims, RepoClaims):
        # for now, we don't allow UI/Frontend tokens to bypass DB check, but eventually we will need
        # to allow that in order to support e2e tests of UI.
        raise InvalidAccessTokenError(
            msg="Not allowed to bypass db check", reason="invalid_bypass", token_type=AccessTokenType.REFRESH_TOKEN  # type: ignore[arg-type]
        )

    repo_claims = cast(RepoClaims, claims)
    customer = Customer.for_user_and_id(user_api_id=repo_claims.user_api_id, customer_id=repo_claims.customer_pk)
    if not customer or not customer.is_internal:
        # Only allowed to bypass db check for internal customers
        raise InvalidAccessTokenError(
            msg=f"Not allowed to bypass db check for customer {claims.customer_pk}", reason="invalid_bypass_customer", token_type=AccessTokenType.REFRESH_TOKEN  # type: ignore[arg-type]
        )


def generate_access_token_from_refresh_token(
    refresh_token_claims: Claims, expiration_delta: datetime.timedelta
) -> tuple[AccessToken, dict[str, str] | None]:
    # See https://tools.ietf.org/html/rfc7519#section-4.1 for Registered Claim Names
    if refresh_token_claims.token_type != AccessTokenType.REFRESH_TOKEN:
        raise ToolchainAssertion("Must provide a refresh token.")
    now = utcnow()
    if expiration_delta < datetime.timedelta(seconds=30):
        raise ToolchainAssertion(f"Invalid expiration_delta: {expiration_delta}")
    expiration_time = now + expiration_delta
    if refresh_token_claims.audience != AccessTokenAudience.FRONTEND_API:
        repo_claims = cast(RepoClaims, refresh_token_claims)
        repo_id = repo_claims.repo_pk
        customer_id = repo_claims.customer_pk
        repo = Repo.get_or_none(id=repo_id, customer_id=customer_id)
        if not repo:
            _logger.warning(f"Can't load {repo_id=} {customer_id=} for token_id={repo_claims.token_id}")
            raise InvalidTokenRequest("Repo N/A.")
        customer = repo.customer
        if not customer.is_active:
            raise InvalidTokenRequest("Inactive customer org.")
        if customer.is_limited:
            raise InvalidTokenRequest("Customer org has limited functionality.")
        ctx = f"aud=api repo={repo_id}"
        extra_data = {"repo_id": repo_id, "customer_id": customer_id}
    else:
        ctx = "aud=frontend"
        extra_data = {}
        repo_id = customer_id = None  # type: ignore[assignment]

    encoder = JWTEncoder(settings.JWT_AUTH_KEY_DATA)
    token_str = encoder.encode_access_token(
        expires_at=expiration_time,
        issued_at=now,
        audience=refresh_token_claims.audience,
        username=refresh_token_claims.username,
        user_api_id=refresh_token_claims.user_api_id,
        repo_id=repo_id,
        customer_id=customer_id,
        is_restricted=False,
        token_id=refresh_token_claims.token_id,
        impersonation_session_id=getattr(
            refresh_token_claims, "impersonation_session_id", None
        ),  # TODO: do this more safely
    )
    _logger.info(
        f"generate_token type=access username={refresh_token_claims.username} {ctx} jid={refresh_token_claims.token_id}  expires_at={expiration_time.isoformat()}"
    )
    return AccessToken(token=token_str, expiration=expiration_time.replace(microsecond=0)), extra_data or None


def generate_restricted_access_token(
    *,
    repo: Repo,
    user: ToolchainUser,
    expiration_delta: datetime.timedelta,
    with_caching: bool,
    token_id: str,
    ctx: str,
) -> AccessToken:
    now = utcnow()
    if expiration_delta < datetime.timedelta(seconds=30):
        raise ToolchainAssertion(f"Invalid expiration_delta: {expiration_delta}")
    expiration_time = now + expiration_delta
    aud = AccessTokenAudience.IMPERSONATE | AccessTokenAudience.BUILDSENSE_API
    if with_caching:
        # Cache r/w until we update our plugin to check permissions and configure pants accordingly
        # Also, only users signed up w/ toolchain are getting tokens in the first place.
        aud |= AccessTokenAudience.CACHE_RW
    encoder = JWTEncoder(settings.JWT_AUTH_KEY_DATA)
    token_str = encoder.encode_access_token(
        expires_at=expiration_time,
        issued_at=now,
        audience=aud,
        username=user.username,
        user_api_id=user.api_id,
        repo_id=repo.pk,
        customer_id=repo.customer_id,
        is_restricted=True,
        token_id=token_id,
    )
    _logger.info(
        f"generate_token type=access_restricted username={user.username} repo={repo.pk} ({repo.slug}) expires_at={expiration_time.isoformat()} {ctx}"
    )
    return AccessToken(token=token_str, expiration=expiration_time.replace(microsecond=0))


_TOKEN_TYPES_STR = {tt.value for tt in AccessTokenType}


def get_token_type(token_str: str) -> AccessTokenType:
    unverified_claims = jwt.get_unverified_claims(token_str)
    token_type_str = unverified_claims.get("type")
    if token_type_str not in _TOKEN_TYPES_STR:
        raise InvalidAccessTokenError(
            msg=f"Invalid token type: {token_type_str}.", reason="UnexpectedType", token_type=None
        )
    return AccessTokenType(token_type_str)


def check_access_token(token_str: str, impersonation_user_api_id: str | None = None) -> Claims:
    ACCESS_TOKEN_CHECK.labels(token_type=AccessTokenType.ACCESS_TOKEN.value).inc()
    try:
        claims_dict, audience = _decode_jwt(token_str, AccessTokenType.ACCESS_TOKEN)
        if impersonation_user_api_id and not audience.can_impersonate:
            raise InvalidAccessTokenError(
                msg="Impersonation request denied.", reason="ImpersonateDenied", token_type=AccessTokenType.ACCESS_TOKEN
            )
        claims, _ = _get_claims(claims_dict, audience, impersonation_user_api_id)
        if claims.token_type != AccessTokenType.ACCESS_TOKEN:
            raise InvalidAccessTokenError(
                msg="Invalid token type.", reason="InvalidType", token_type=AccessTokenType.ACCESS_TOKEN
            )
    except InvalidAccessTokenError as error:
        _report_token_check_failure(error)
        raise
    _report_token_time_left(claims_dict, claims)
    return claims


def _report_token_time_left(claims_dict, claims) -> None:
    time_left = claims_dict["exp"] - int(utcnow().timestamp())
    if AccessTokenAudience.FRONTEND_API in claims.audience:
        api = "ui"
    elif AccessTokenAudience.CACHE_RO in claims.audience or AccessTokenAudience.CACHE_RW in claims.audience:
        api = "api_cache"
    else:
        api = "api"
    ACCESS_TOKEN_TIME_LEFT.labels(api=api).observe(time_left)
    if time_left <= LOW_EXPIRATION_THRESHOLD_SECONDS:
        _logger.info(f"accepted access token w/ {time_left=} {api=} user={claims.user_api_id}")


def _decode_jwt(token_str: str, token_type: AccessTokenType) -> tuple[dict, AccessTokenAudience]:
    key_data: JWTSecretData = settings.JWT_AUTH_KEY_DATA
    key = _get_key(key_data, token_str, token_type)
    try:
        claims_dict = jwt.decode(
            token_str, key=key.secret_key, algorithms=[key.algorithm], options=dict(verify_aud=False)
        )
    except jwt.JWTError as error:
        raise InvalidAccessTokenError(
            msg=f"Failed to decode token {error!r}", reason=type(error).__name__, token_type=token_type, error=error
        )
    audience = AccessTokenAudience.from_api_names(claims_dict["aud"])
    claims_dict["kid"] = key.key_id
    return claims_dict, audience


def _get_key(key_data: JWTSecretData, token_str: str, token_type: AccessTokenType) -> JWTSecretKey:
    try:
        unverified_headers = jwt.get_unverified_header(token_str)
    except jwt.JWTError as error:
        raise InvalidAccessTokenError(
            msg=f"Failed to decode token {error!r}", reason=type(error).__name__, token_type=token_type, error=error
        )
    key_id = unverified_headers.get("kid")
    if not key_id:
        raise InvalidAccessTokenError(msg="Failed to decode token", reason="missing_key_id", token_type=token_type)
    key = key_data.get_for_key_id(str(key_id), token_type)
    if not key:
        raise InvalidAccessTokenError(
            msg=f"Failed to decode token key_id={key_id}", reason="invalid_key_id", token_type=token_type
        )
    return key


def _report_token_check_failure(error: InvalidAccessTokenError) -> None:
    _logger.warning(f"token_failure error={error.reason} token_type={error.token_type} {error.get_message()}")
    # Sending token_id and or customer_id has the potential of causing high cardinality issues.
    # However, we don't expeect a lot of token errors over time and we need to ability to silence token failure alerts based on a given customer or token.
    ACCESS_TOKEN_CHECK_FAILURE.labels(
        error_type=error.reason, token_type=error.token_type, token_id=error.token_id, customer=error.customer_id
    ).inc()
