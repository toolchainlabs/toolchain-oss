# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth import login
from django.http import HttpResponseBadRequest, HttpResponseForbidden, HttpResponseRedirect
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import RedirectView, TemplateView
from duo_universal.client import Client
from social_core.actions import do_auth, do_complete

from toolchain.django.site.auth.toolchain_github import ToolchainGithubOAuth2
from toolchain.django.site.models import ToolchainUser
from toolchain.toolshed.config import DuoAuthConfig
from toolchain.toolshed.cookie import AuthCookie
from toolchain.toolshed.url_names import URLNames
from toolchain.users.models import ImpersonationSession
from toolchain.users.ui.impersonation_util import user_can_be_impersonated

_logger = logging.getLogger(__name__)


class ToolshedIndexView(TemplateView):
    view_type = "app"
    template_name = "admin/toolshed_index.html"


class AdminLoginView(TemplateView):
    view_type = "app"
    template_name = "admin/github_login.html"

    def __init__(self, *args, **kwargs):
        kwargs["extra_context"].update(title="Log in")
        super().__init__(*args, **kwargs)

    def get(self, request, **kwargs):
        user = request.user
        if user.is_active and user.is_staff and not AuthCookie.exists(request, user.api_id):
            redirect_url = reverse(URLNames.DUO_AUTH)
            _logger.info(f"Logged {user=} in but no duo. redirect {redirect_url=}.")
            return HttpResponseRedirect(redirect_url)
        return super().get(request, **kwargs)

    def get_context_data(self, **kwargs):
        request = self.request
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "app_path": request.get_full_path(),
                "username": request.user.get_username(),
                "github_login_url": reverse(URLNames.GITHUB_AUTH_BEGIN),
            }
        )
        return context


def _get_new_duo_client(request) -> Client:
    cfg = settings.DUO_CONFIG
    redirect_uri = request.build_absolute_uri(location=reverse(URLNames.DUO_CALLBACK))
    return Client(
        client_id=cfg.client_id,
        client_secret=cfg.client_secret,
        host=cfg.host,
        redirect_uri=redirect_uri,
    )


class DuoAuthCallbackView(TemplateView):
    template_name = "admin/duo_auth_fail.html"

    def _auth_error(self, error: str):
        context = self.get_context_data()
        context["error"] = "Sorry, we couldn't authenticate you."
        return self.render_to_response(context, status=HttpResponseBadRequest.status_code)

    def get(self, request):
        session = request.session
        user = request.user
        state = request.GET.get("state")
        code = request.GET.get("duo_code")

        if not code or not state:
            _logger.warning(f"missing redirect params: {request.GET=}")
            return self._auth_error("Invalid redirect params")

        if "state" in session and "username" in session:
            saved_state = session["state"]
            username = session["username"]
        else:
            _logger.warning(f"missing state values: {session.keys()}")
            return self._auth_error("Missing session state values")

        # Ensure nonce matches from initial request
        if state != saved_state:
            _logger.warning(f"invalid state. expected: {saved_state} got: {state}")
            return self._auth_error("Duo state does not match saved state")

        duo_client = _get_new_duo_client(request)
        decoded_token = duo_client.exchange_authorization_code_for_2fa_result(code, username)
        _logger.info(f"duo auth token: {decoded_token}")
        response = HttpResponseRedirect(reverse(URLNames.INDEX))
        AuthCookie.store_cookie(response, user.api_id)
        _logger.info(f"User: {user} authenticated with duo 2fa. {response.cookies.keys()=}")
        return response


class DuoAuthView(RedirectView):
    view_type = "app"

    @property
    def _duo_config(self) -> DuoAuthConfig:
        return settings.DUO_CONFIG

    def get_redirect_url(self, *args, **kwargs):
        user = self.request.user
        if not user.is_active or not user.is_staff:
            _logger.info("DuoAuthView. user not logged in.")
            return reverse(URLNames.LOGIN)
        session = self.request.session
        username = user.username
        duo_client = _get_new_duo_client(self.request)
        duo_client.health_check()
        state = duo_client.generate_state()
        session["state"] = state
        session["username"] = username
        prompt_uri = duo_client.create_auth_url(username, state)
        _logger.info(f"Redirect user to duo: {prompt_uri=}")
        return prompt_uri

    def _auth_error(self, context, status):
        context["error"] = "Sorry, we couldn't authenticate you."
        return self.render_to_response(context, status=status)


def _get_github_backend(request):
    redirect_uri = reverse(URLNames.GITHUB_AUTH_COMPLETE)
    return ToolchainGithubOAuth2.for_request(request, redirect_uri=redirect_uri)


@never_cache
def github_auth(request):
    github_backend = _get_github_backend(request)
    return do_auth(github_backend)


@never_cache
@csrf_exempt
def github_complete(request, *args, **kwargs):
    def _do_django_login(backend, user, social_user):
        user.backend = backend.full_backend_name
        # Log the user in, creating a new session.
        login(request, user)

    github_backend = _get_github_backend(request)
    return do_complete(
        github_backend, _do_django_login, user=request.user, request=request, *args, **kwargs  # noqa: B026
    )


@never_cache
def request_ui_impersonation(request, user_api_id):
    """Begin a UI user impersonation session.

    We do this by:
    1. Create an impersionation session object, marked as `started=False`
    2. Redirecting into the users service, where we check the database for the corresponding session object
    3. The users service is responsible for actually establishing the impersonation session.
    """
    # Perform last-minute check that this impersonation is OK to be requested; raise a 403 if not.
    to_impersonate = ToolchainUser.get_by_api_id(user_api_id)
    if not to_impersonate:
        return HttpResponseForbidden("The requested user does not exist.")
    user_can_be_impersonated(to_impersonate, raise_http_forbidden=True, impersonator_api_id=request.user.api_id)
    session_id = ImpersonationSession.create_and_return_id(user_api_id, request.user.api_id)
    return HttpResponseRedirect(f"{settings.MAIN_SITE_PREFIX}/impersonate/start/{ session_id }/")
