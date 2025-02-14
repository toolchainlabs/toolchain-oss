# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from urllib.parse import urlencode, urlparse, urlunparse

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import update_last_login
from django.contrib.auth.views import LogoutView
from django.core.exceptions import PermissionDenied
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseRedirect,
    QueryDict,
)
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.generic import RedirectView, TemplateView
from social_core.actions import do_auth, do_complete

from toolchain.django.auth.constants import REFRESH_TOKEN_COOKIE_NAME
from toolchain.django.site.auth.toolchain_bitbucket import ToolchainBitbucketOAuth2
from toolchain.django.site.auth.toolchain_github import ToolchainGithubOAuth2
from toolchain.django.site.models import ToolchainUser
from toolchain.django.site.utils.request_utils import get_client_ip
from toolchain.users.constants import SUPPORT_EMAIL_ADDR
from toolchain.users.jwt.cookie import add_refresh_token_cookie
from toolchain.users.models import ImpersonationSession, UserTermsOfServiceAcceptance
from toolchain.users.ui.impersonation_util import user_can_be_impersonated
from toolchain.users.ui.url_names import URLNames

_logger = logging.getLogger(__name__)

_KNOWN_USER_COOKIE = "tcuser"


class ToolchainLoginView(TemplateView):
    view_type = "app"
    template_name = "users/login.html"
    _DEFAULT_LOGIN_PROVIDERS = (
        ("github", "black", URLNames.GITHUB_AUTH_BEGIN),
        # Disabled bitbucket provider for now since we don't have any customers using it
        # ("bitbucket", "blue", URLNames.BITBUCKET_AUTH_BEGIN),
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        next_url = self.request.GET.get("next")
        referer_url = urlparse(self.request.headers.get("referer", ""))
        is_from_infosite = referer_url.scheme == "https" and referer_url.netloc.lower() == "toolchain.com"
        is_tc_user = self.request.COOKIES.get(_KNOWN_USER_COOKIE) == "1"
        show_onboarding = self.request.GET.get("onboarding") == "1" or (is_from_infosite and not is_tc_user)
        providers = list(self._DEFAULT_LOGIN_PROVIDERS)  # defensive copy
        login_options = []
        for name, color, url_name in providers:
            login_url = reverse(url_name)
            if next_url:
                next_query_params = urlencode({"next": next_url})
                login_url = f"{login_url}?{next_query_params}"
            login_options.append((name, name.capitalize(), f"{color}-button", login_url))
        context.update(
            login_options=login_options,
            show_onboarding=show_onboarding,
            pants_version="2.12",
            docs_link="https://docs.toolchain.com/docs",
            onboarding_link="https://www.pantsbuild.org/docs/getting-started",
        )
        return context


def _get_bitbucket_backend(request):
    redirect_uri = reverse(URLNames.BITBUCKET_AUTH_COMPLETE)
    return ToolchainBitbucketOAuth2.for_request(request, redirect_uri=redirect_uri)


def _get_github_backend(request):
    redirect_uri = reverse(URLNames.GITHUB_AUTH_COMPLETE)
    return ToolchainGithubOAuth2.for_request(request, redirect_uri=redirect_uri)


@never_cache
def bitbucket_auth(request):
    bitbucket_backend = _get_bitbucket_backend(request)
    return do_auth(bitbucket_backend)


@never_cache
def github_auth(request):
    github_backend = _get_github_backend(request)
    return do_auth(github_backend)


def _finalize_user_login(request, user, backend):
    user.backend = backend.full_backend_name
    request.user = user
    update_last_login(__name__, user)


@never_cache
@csrf_exempt
def bitbucket_complete(request, *args, **kwargs):
    def finish_login(backend, user, social_user):
        _finalize_user_login(request, user, backend)

    bitbucket_backend = _get_bitbucket_backend(request)
    response = do_complete(
        bitbucket_backend, finish_login, user=request.user, request=request, *args, **kwargs  # noqa: B026
    )
    return _finish_user_auth("bitbucket_complete", request, response)


@never_cache
@csrf_exempt
def github_complete(request, *args, **kwargs):
    def finish_login(backend, user, social_user):
        _finalize_user_login(request, user, backend)

    setup_action = request.GET.get("setup_action")
    if setup_action:
        # Redirect after GitHub app install
        _logger.info(f"github_complete after app install {setup_action=}")
        return HttpResponseRedirect("/")

    github_backend = _get_github_backend(request)
    response = do_complete(
        github_backend, finish_login, user=request.user, request=request, *args, **kwargs  # noqa: B026
    )
    return _finish_user_auth("github_complete", request, response)


github_auth.view_type = "app"
github_complete.view_type = "app"


def _finish_user_auth(view_name: str, request, response):
    user = request.user
    request.session.flush()
    if not user.is_authenticated:
        _logger.warning("finish_user_auth - user not authenticated.")
        return response
    accepted_tos = UserTermsOfServiceAcceptance.has_accepted(user.api_id)
    _logger.info(f"{view_name} {user=} status={response.status_code} {accepted_tos=} url={response.url}")
    if not accepted_tos:
        tos_redirect_url = _get_tos_redirect_url(next_url=response.url)
        _logger.info(f"User {user} needs to accept TOS, redirecting to: {tos_redirect_url}")
        response = redirect(to=tos_redirect_url)
    add_refresh_token_cookie(response=response, user=user)
    add_known_user_cookie(response)
    return response


def _get_tos_redirect_url(next_url: str) -> str:
    # Based on django.contrib.auth.views:redirect_to_login
    tos_url = reverse(URLNames.TOS)
    if not next_url or next_url == "/":
        return tos_url
    tos_url_parts = list(urlparse(tos_url))
    querystring = QueryDict(tos_url_parts[4], mutable=True)
    querystring["next"] = next_url
    tos_url_parts[4] = querystring.urlencode(safe="/")
    return urlunparse(tos_url_parts)


def _delete_refresh_token_cookie(response):
    response.delete_cookie(REFRESH_TOKEN_COOKIE_NAME)


def add_known_user_cookie(response: HttpResponse) -> None:
    is_prod = settings.TOOLCHAIN_ENV.is_prod
    response.set_cookie(_KNOWN_USER_COOKIE, value="1", secure=is_prod, httponly=False, samesite="Lax")


class ToolchainLogoutView(LogoutView):
    view_type = "app"

    @method_decorator(never_cache)
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        _delete_refresh_token_cookie(response)
        return response


class UserAccessDeniedView(TemplateView):
    view_type = "app"
    template_name = "users/error.html"

    def render_to_response(self, context, **response_kwargs):
        return super().render_to_response(context, status=HttpResponseForbidden.status_code, **response_kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "error_message": "You are not currently registered as a Toolchain user.",
                "contact_page_link": "https://toolchain.com/contact",
            }
        )
        return context


@never_cache
def impersonate(request, session_id: str):
    """Logs into the system impersonating a user based on the given `session_id`, which identifies the user to be
    impersonating, as well as the user that requested the session."""
    response = HttpResponseRedirect("/")

    # Impersonation is only available to superusers
    if not request.user.is_staff:
        _logger.warning(f"Non-superuser {request.user} wanted to start impersonation for {session_id}. Giving a 404.")
        raise Http404()

    # Users may only start a session that:
    # - has not already been started
    # - was requested less than 2 minutes ago (allowing for time to log in).
    # - was requested by the current user
    session = ImpersonationSession.get_fresh_session_for_impersonator_or_none(session_id, request.user.api_id)

    if session is None:
        raise Http404()
    user_api_id = session.user_api_id
    user_to_impersonate = ToolchainUser.get_by_api_id(user_api_id)
    if user_to_impersonate is None:
        _logger.warning(
            f"User {request.user} requested a session to impersonate another inactive user {user_api_id}. Giving a 403."
        )
        raise PermissionDenied()

    # Raise HTTP 403 if impersonation target is a staff member, or is the logged-in user
    user_can_be_impersonated(user_to_impersonate, raise_http_forbidden=True, impersonator_api_id=request.user.api_id)
    session.start()
    add_refresh_token_cookie(response=response, user=user_to_impersonate, impersonation_session=session_id)
    return response


impersonate.view_type = "app"


class UserTOSView(TemplateView):
    view_type = "app"
    template_name = "users/tos.html"

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def _redirect_next(self, request) -> HttpResponseRedirect:
        # This works if the request is a POST request too, as long as it has a query string.
        next = request.GET.get("next") or "/"
        return HttpResponseRedirect(next)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["tos_version"] = settings.TOS_VERSION
        return ctx

    def get(self, request):
        user = request.user
        force_show = (
            request.GET.get("force", "") == "1"
        )  # Allow showing the TOS page even if TOS has been accepted (for testing purposes)
        accepted_tos = UserTermsOfServiceAcceptance.has_accepted(user.api_id)
        if accepted_tos and not force_show:
            return self._redirect_next(request)
        return super().get(request)

    @method_decorator(csrf_protect)
    def post(self, request):
        user = request.user
        tos_version = request.POST.get("tos-version")
        if tos_version != settings.TOS_VERSION:
            _logger.warning(f"Invalid TOS version: {tos_version}")
            return HttpResponseBadRequest("Invalid request")
        client_ip = get_client_ip(request)
        if not client_ip:
            _logger.warning(f"can't determine IP address: {request.headers}")
            return HttpResponseBadRequest("Invalid request headers")
        UserTermsOfServiceAcceptance.accept_tos(
            user_api_id=user.api_id,
            tos_version=tos_version,
            client_ip=client_ip,
            user_email=user.email,
            request_id=request.request_id,
        )
        return self._redirect_next(request)


class NoOrgView(TemplateView):
    view_type = "app"
    template_name = "users/no-org.html"
    _DOCS_LINK = "https://docs.toolchain.com/docs/getting-started-with-toolchain"

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            install_github_link=reverse(URLNames.GITHUB_APP_INSTALL),
            support_email=SUPPORT_EMAIL_ADDR,
            docs_link=self._DOCS_LINK,
        )
        return ctx


class InstallGithubAppView(RedirectView):
    view_type = "app"
    permanent = False
    _INSTALL_LINK = settings.TOOLCHAIN_GITHUB_APP_INSTALL_LINK

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        response = super().dispatch(*args, **kwargs)
        # We logout the user since we need to re-evaluate the user's org membership when they come back.
        # and we do that only during login (as part of the social auth pipeline).
        _delete_refresh_token_cookie(response)
        return response

    def get_redirect_url(self, *args, **kwargs):
        _logger.info(f"start_install_github_app: {self._INSTALL_LINK}")
        return self._INSTALL_LINK
