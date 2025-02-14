# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from urllib.parse import ParseResult, parse_qsl, urlencode, urlparse, urlunparse

from django.conf import settings
from django.forms import BooleanField, CharField, JSONField, URLField, ValidationError
from django.http import HttpResponseBadRequest, HttpResponseForbidden, HttpResponseRedirect
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from toolchain.base.datetime_tools import utcnow
from toolchain.django.auth.constants import AccessTokenAudience
from toolchain.django.forms.base_form import ToolchainForm
from toolchain.django.site.models import Repo, ToolchainUser
from toolchain.django.site.utils.response_utils import render_template_response
from toolchain.django.util.view_util import ToolchainLoginRequiredMixin
from toolchain.github_integration.client.repo_clients import GithubRepoInfoClient
from toolchain.users.constants import CONTACT_TOOLCHAIN_MESSAGE
from toolchain.users.jwt.authentication import AuthenticationFromInternalHeaders, RefreshTokenAuthentication
from toolchain.users.jwt.config import JWTConfig
from toolchain.users.jwt.cookie import add_refresh_token_cookie
from toolchain.users.jwt.utils import (
    AccessToken,
    InvalidTokenRequest,
    generate_access_token_from_refresh_token,
    generate_refresh_token,
    generate_restricted_access_token,
)
from toolchain.users.models import (
    AccessTokenExchangeCode,
    AuthProvider,
    ExchangeCodeData,
    GithubRepoConfig,
    RestrictedAccessToken,
    UserAuth,
    UserCustomerAccessConfig,
)

_logger = logging.getLogger(__name__)

_DESKTOP_TOKEN_TTL = datetime.timedelta(days=180)
_CI_TOKEN_TTL = datetime.timedelta(days=365)
_CLASS_LIST = tuple[type, ...]


@dataclass(frozen=True)
class ResolveCIForTokenInfo:
    user: ToolchainUser
    key: str
    tokens_count: int


class AccessTokenExchangeForm(ToolchainForm):
    code = CharField(required=True)
    allow_impersonation = BooleanField(required=False)
    desc = CharField(required=False)
    remote_execution = BooleanField(required=False)


class AccessTokenAuthForm(ToolchainForm):
    allow_unexpected_fields = True  # client can pass other arguments that will be passed back on redirect

    repo = CharField(required=True)
    redirect_uri = URLField(required=False)
    headless = BooleanField(required=False)

    def clean_redirect_uri(self):
        uri = self.cleaned_data["redirect_uri"]
        if not uri:
            return uri
        redirect_uri = urlparse(uri)
        netloc = redirect_uri.netloc
        host, _, _ = netloc.partition(":")
        if host.lower() not in ["localhost", "127.0.0.1"]:
            raise ValidationError("Must redirect to localhost")
        return redirect_uri

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("headless") and not cleaned.get("redirect_uri"):
            raise ValidationError("redirect_uri is required when not in headless mode", code="invalid")


class AccessTokenAuthView(ToolchainLoginRequiredMixin, APIView):
    # ToolchainLoginRequiredMixin must be first!
    view_type = "app"
    authentication_classes = (AuthenticationFromInternalHeaders,)

    def get(self, request):
        user = request.user
        form = AccessTokenAuthForm(request.query_params)
        if not form.is_valid():
            _logger.warning(f"Invalid data provides {request.query_params} {form.errors}")
            return self._render_error_page(request, "Invalid params")
        headless = form.cleaned_data["headless"]
        redirect_uri = form.cleaned_data["redirect_uri"]
        repo_fn = form.cleaned_data["repo"]
        if "/" in repo_fn:
            customer_slug, _, repo_slug = repo_fn.partition("/")
            repo = Repo.get_or_none_for_slugs_and_user(repo_slug=repo_slug, customer_slug=customer_slug, user=user)
        else:
            # Backward compatibility, we will need to get rid of it after toolchain pant plugin has been updated and all the customers
            # updated to it.
            repo = Repo.get_or_none_for_slug(slug=repo_fn, user=user)
        if not repo:
            _logger.warning(f"Repo {repo_fn} not associated with user {user}")
            if headless:
                return self._render_error_page(request, "Invalid repo for user")
            redirect_to = _get_redirect_uri(redirect_uri, error="Invalid repo for user")
            return HttpResponseRedirect(redirect_to)
        code = AccessTokenExchangeCode.create_for_user(user=user, repo_id=repo.pk)
        if headless:
            return render_template_response(
                request=request,
                status=201,
                template="users/headless_new.html",
                context={"access_code_data": code},
            )
        query_params = request.query_params.dict()
        del query_params["redirect_uri"]
        query_params.pop("repo", None)
        redirect_to = _get_redirect_uri(redirect_uri, code=code, **query_params)
        return HttpResponseRedirect(redirect_to)

    def _render_error_page(self, request, message: str):
        return render_template_response(
            request=request,
            status=HttpResponseBadRequest.status_code,
            template="users/error.html",
            context={"error_message": message},
        )


class AccessTokenExchangeView(APIView):
    view_type = "app"
    authentication_classes: _CLASS_LIST = tuple()
    permission_classes: _CLASS_LIST = (AllowAny,)

    def post(self, request):
        form = AccessTokenExchangeForm(request.data)
        if not form.is_valid():
            _logger.warning(f"Bad input in form: {form.errors}")
            return Response(
                {"message": form.errors.as_text(), "errors": form.errors.get_json_data()},
                status=HttpResponseBadRequest.status_code,
            )
        code = form.cleaned_data["code"]
        description = form.cleaned_data["desc"]
        exchange_code_data = AccessTokenExchangeCode.use_code(code=code)
        if not exchange_code_data:
            return Response({"message": "Invalid exchange code"}, status=HttpResponseBadRequest.status_code)
        allow_impersonation = form.cleaned_data["allow_impersonation"]
        remote_execution = form.cleaned_data["remote_execution"]
        user = ToolchainUser.get_by_api_id(exchange_code_data.user_api_id)
        if not user:
            _logger.warning(f"User not found: {exchange_code_data.user_api_id} for {code=}")
            return Response({"message": "Invalid user."}, status=HttpResponseForbidden.status_code)
        try:
            token_dict = _create_refresh_token_for_exchange_code(
                exchange_code_data,
                with_impersonation=allow_impersonation,
                with_remote_execution=remote_execution,
                user=user,
                description=description,
            )
        except InvalidTokenRequest as error:
            return Response({"message": error.msg}, status=error.status_code)
        return Response(token_dict)


class AccessTokenRefreshView(APIView):
    view_type = "app"
    authentication_classes = (RefreshTokenAuthentication,)

    def post(self, request):
        claims = request.auth
        user = request.user
        has_caching = claims.audience.has_caching
        has_remote_exec = claims.audience.has_remote_execution
        token_ttl = _get_ttl_for_token(claims.audience)
        try:
            access_token, extra_data = generate_access_token_from_refresh_token(claims, expiration_delta=token_ttl)
        except InvalidTokenRequest as error:
            _logger.warning(f"invalid token request: {error}")
            return Response(
                status=HttpResponseForbidden.status_code,
                data={"detail": f"Invalid token request: {error}\n{CONTACT_TOOLCHAIN_MESSAGE}", "rejected": True},
            )
        extra_kwargs = extra_data or {}

        response_data = _create_token_response_dict(
            access_token=access_token, has_caching=has_caching, has_remote_exec=has_remote_exec, **extra_kwargs
        )
        response = Response(response_data)
        if claims.audience.has_frontend_api:
            add_refresh_token_cookie(response=response, user=user)
        return response


def _get_ttl_for_token(audience: AccessTokenAudience) -> datetime.timedelta:
    # Pants remote client/auth plugin doesn't support renewing tokens during pants run, so when caching is enabled we need to allocate
    # a token that can last for the entire pants run.
    config: JWTConfig = settings.JWT_CONFIG
    if audience.has_remote_execution:
        return config.token_with_remote_exec_ttl
    if audience.has_caching:
        return config.token_with_caching_ttl
    return config.default_token_ttl


class RestrictedAccessTokenForm(ToolchainForm):
    repo_slug = CharField(required=True)
    env = JSONField(required=True)

    def clean_repo_slug(self):
        repo_slug = self.cleaned_data["repo_slug"]
        account, _, repo = repo_slug.partition("/")
        if not account or not repo:
            raise ValidationError("Invalid repo slug")
        return account, repo

    def clean_env(self):
        env = self.cleaned_data["env"]
        if not isinstance(env, dict):
            raise ValidationError("Invalid env vars data")
        if len(env) < 3:
            raise ValidationError("Missing env vars data")
        return env


class RepoConfig:
    max_build_tokens = 3
    started_treshold = datetime.timedelta(minutes=6)
    token_ttl = datetime.timedelta(minutes=3)


class RestrictedAccessTokenView(APIView):
    view_type = "app"
    authentication_classes: _CLASS_LIST = tuple()
    permission_classes: _CLASS_LIST = (AllowAny,)

    def post(self, request):
        form = RestrictedAccessTokenForm(request.data)
        if not form.is_valid():
            _logger.warning(f"Bad input in form: {form.errors}")
            return Response({"errors": form.errors.get_json_data()}, status=HttpResponseBadRequest.status_code)

        customer_slug, repo_slug = form.cleaned_data["repo_slug"]
        repo = Repo.get_for_slugs_or_none(customer_slug=customer_slug, repo_slug=repo_slug)
        if not repo:
            slug = f"{customer_slug}/{repo_slug}"
            _logger.warning(f"repo not found: {slug}")
            return Response(
                {
                    "errors": {
                        "repo_slug": [
                            {
                                "code": "not_found",
                                "message": f"repo not available at {slug}",
                            }
                        ]
                    }
                },
                status=HttpResponseBadRequest.status_code,
            )
        # We now have hard coded default value, we will eventually remove it.
        cfg = GithubRepoConfig.for_repo(repo_id=repo.id) or RepoConfig()
        ci_env = form.cleaned_data["env"]
        ci_token_info = _process_ci_data(repo, cfg, ci_data=ci_env)
        if not ci_token_info:
            # See AuthClient._process_response
            return Response({"rejected": True}, status=403)
        token_id = RestrictedAccessToken.allocate(key=ci_token_info.key, repo_id=repo.pk)
        access_token = generate_restricted_access_token(
            repo=repo,
            user=ci_token_info.user,
            with_caching=True,  # TODO: hard coded for now, but we should look at the GithubRepoConfig to determine that.
            expiration_delta=cfg.token_ttl,
            token_id=token_id,
            ctx=f"count={ci_token_info.tokens_count}/{cfg.max_build_tokens} key={ci_token_info.key} {ci_env=}",
        )
        resp_data = _create_token_response_dict(
            access_token=access_token,
            repo_id=repo.id,
            customer_id=repo.customer_id,
            has_caching=True,
            has_remote_exec=False,
        )
        return Response(resp_data)


def _create_refresh_token_for_exchange_code(
    exchange_code_data: ExchangeCodeData,
    with_impersonation: bool,
    with_remote_execution: bool,
    user: ToolchainUser,
    description: str,
) -> dict:
    repo = Repo.get_for_id_and_user_or_none(repo_id=exchange_code_data.repo_id, user=user)
    _logger.info(
        f"request refresh token for {user} on {repo} {with_impersonation=} {with_remote_execution=} {description=}"
    )
    if not repo:
        _logger.warning(f"Invalid repo for {exchange_code_data.description}")
        raise InvalidTokenRequest("Repo N/A")
    customer = repo.customer
    if with_remote_execution and customer.slug not in settings.ALLOWED_REMOTE_EXEC_CUSTOMERS_SLUGS:
        _logger.warning(f"Customer {customer} is not allowed to use remote execution")
        raise InvalidTokenRequest("Remote execution permission denided", status_code=HttpResponseForbidden.status_code)

    allowed_audiences = UserCustomerAccessConfig.get_audiences_for_user(
        customer_id=repo.customer_id, user_api_id=user.api_id
    )
    # Right now we only use this logic for the pants auth flow (tc/pants/auth/rules), so it is ok to hard code this scope.
    requested_audience = AccessTokenAudience.for_pants_client(
        with_impersonation=with_impersonation,
        internal_toolchain=False,
        with_remote_execution=with_remote_execution,
    )
    audience = AccessTokenAudience.merge(allowed=allowed_audiences, requested=requested_audience)
    if not audience:
        _logger.warning(
            f"None of the requested permissions are allowed. customer_id={repo.customer_id} requested={requested_audience} allowed={allowed_audiences}"
        )
        raise InvalidTokenRequest("Missing permissions", status_code=HttpResponseForbidden.status_code)
    if with_impersonation and not audience.can_impersonate:
        _logger.warning(
            f"Impersonation requested but user access config doesn't allow it. customer_id={repo.customer_id} {user=} {allowed_audiences=}"
        )
        raise InvalidTokenRequest("Impersonation not allowed.", status_code=HttpResponseForbidden.status_code)
    expiration_time = utcnow() + (_CI_TOKEN_TTL if with_impersonation else _DESKTOP_TOKEN_TTL)
    access_token_str = generate_refresh_token(
        user=user,
        repo_pk=repo.pk,
        customer=customer,
        expiration_time=expiration_time,
        audience=audience,
        description=description,
    )
    _logger.info(f"generate_refresh_token user={user.username} repo={repo.slug} audience={audience}")
    return {
        "access_token": access_token_str,
        "user": user.username,
        "repo": repo.slug,
        "expires_at": expiration_time.isoformat(),
    }


def _get_redirect_uri(parsed_url, **extra_params):
    query = dict(parse_qsl(parsed_url.query))
    query.update(extra_params)
    parts = parsed_url._asdict()
    parts["query"] = urlencode(query)
    return urlunparse(ParseResult(**parts))


def _process_ci_data(repo: Repo, cfg: RepoConfig, ci_data: dict) -> ResolveCIForTokenInfo | None:
    # Initial implementation is super simple.
    client = GithubRepoInfoClient.for_repo(settings, customer_id=repo.customer_id, repo_id=repo.id)
    ci_details = client.resolve_ci_build(ci_data, started_treshold=cfg.started_treshold)
    if not ci_details:
        return None
    user_auth = UserAuth.get_by_user_id(provider=AuthProvider.GITHUB, user_id=ci_details.user_id)
    if not user_auth:
        _logger.warning(f"Unknown github user for build github_user_id={ci_details.user_id} {repo=} {ci_data}")
        return None
    user = ToolchainUser.get_by_api_id(user_auth.user_api_id, customer_id=repo.customer_id)
    if not user:
        _logger.warning(
            f"{user_auth} not associated with customer  github_user_id={ci_details.user_id} {repo=} {ci_data}"
        )
        return None
    # We need more checks here, but making sure the user is in our system is a good start
    # We probably want to make sure the user is associated with repo.customer
    tokens_count = RestrictedAccessToken.tokens_for_key(ci_details.key)
    if tokens_count >= cfg.max_build_tokens:
        _logger.warning(f"max access tokens reached for key={ci_details.key} tokens={tokens_count} {ci_data=}")
        return None
    return ResolveCIForTokenInfo(user=user, key=ci_details.key, tokens_count=tokens_count)


def _create_token_response_dict(
    access_token: AccessToken,
    repo_id: str | None = None,
    customer_id: str | None = None,
    has_caching: bool = False,
    has_remote_exec: bool = False,
) -> dict:
    data = {}
    token_data = {
        "access_token": access_token.token,
        "expires_at": access_token.expiration.isoformat(),
    }
    if repo_id and customer_id:
        token_data.update({"repo_id": repo_id, "customer_id": customer_id})
    if has_caching:
        proxy_addr = settings.TOOLCHAIN_REMOTE_CACHE_ADDRESS
        # Hard coded for now, later on we can have different hosts per customer.
        # See: src/python/toolchain/pants/auth/client.py:TokenAndConfig.from_response_json
        data["remote_cache"] = {"address": proxy_addr}  # type: ignore[assignment]
        if has_remote_exec:
            data["remote_exec"] = {"address": proxy_addr}  # type: ignore[assignment]
    data["token"] = token_data
    return data
