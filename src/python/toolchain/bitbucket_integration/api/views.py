# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from urllib.parse import urlparse

import httpx
from django.conf import settings
from django.http import Http404, HttpResponseBadRequest, HttpResponseNotFound
from jose import jwt
from rest_framework.response import Response
from rest_framework.views import APIView

from toolchain.base.toolchain_error import ToolchainAssertion, ToolchainError
from toolchain.bitbucket_integration.common.events import AppInstallEvent, AppUninstallEvent, WebhookEvent
from toolchain.bitbucket_integration.hook_handlers import HookHandleFailure, run_handler
from toolchain.bitbucket_integration.models import BitbucketAppInstall
from toolchain.bitbucket_integration.repo_data_store import BitbucketRepoDataStore
from toolchain.django.site.models import Customer

_logger = logging.getLogger(__name__)


class InvalidCustomerError(ToolchainError):
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class BaseBitbucketIntegrationView(APIView):
    view_type = "internal"


class AppInstallView(BaseBitbucketIntegrationView):
    def handle_exception(self, exc):
        if isinstance(exc, InvalidCustomerError):
            _logger.warning(exc)
            return Response(status=exc.status_code)
        if isinstance(exc, HookHandleFailure):
            _logger.warning(exc)
            return Response(status=403)
        return super().handle_exception(exc)

    def _get_bitbucket_customer(self, account_name: str) -> Customer:
        customer = Customer.for_slug(slug=account_name.lower())
        if not customer:
            raise InvalidCustomerError(
                f"no active customer for {account_name}", status_code=HttpResponseNotFound.status_code
            )
        if customer.scm_provider != Customer.Scm.BITBUCKET:
            raise InvalidCustomerError(
                f"{customer=} is not a using bitbucket: {customer.scm_provider=}",
                status_code=HttpResponseBadRequest.status_code,
            )
        return customer

    def check_jwt(self, jwt_str: str, audience):
        try:
            jwt.decode(
                token=jwt_str, key=settings.BITBUCKET_CONFIG.secret, algorithms=jwt.ALGORITHMS.HS256, audience=audience
            )
        except jwt.JWTError as error:
            raise HookHandleFailure(f"failed to decode jwt: {jwt_str} {error!r}") from error

    def post(self, request):
        install_event = AppInstallEvent.from_json(request.data)
        self.check_jwt(install_event.jwt, audience=install_event.client_key)
        account_name = install_event.account_name
        if install_event.account_type == "user" and not account_name:
            account_name = _get_account_name(install_event.account_url)
        customer = self._get_bitbucket_customer(account_name)
        BitbucketAppInstall.install(customer_id=customer.id, app_install=install_event, account_name=account_name)
        return Response(status=201)

    def patch(self, request):
        uninstall_event = AppUninstallEvent.from_json(request.data)
        self.check_jwt(uninstall_event.jwt, audience=uninstall_event.client_key)
        account_name = uninstall_event.account_name
        if uninstall_event.account_type == "user" and not account_name:
            account_name = _get_account_name(uninstall_event.account_url)
        customer = self._get_bitbucket_customer(account_name)
        uninstalled = BitbucketAppInstall.uninstall(customer_id=customer.id, app_uninstall=uninstall_event)
        return Response(status=201 if uninstalled else 200)


def _get_account_name(url: str) -> str:
    # This is a hacky solution, but keep in mind that we don't want to support personal accounts on bitbucket.
    # However, in order to get our Bitbucket integration approved for the Atlassian, we have to support it
    # mostly because the person testing it uses his personal testing account and not a team account.
    # Once our app is approved we will probably change the logic to reject those account types silently from a user POV,
    # but we probably want to have a Sentry error if we hit this use case.
    parsed_url = urlparse(url)
    if parsed_url.scheme != "https" or parsed_url.netloc != "api.bitbucket.org":
        raise ToolchainAssertion(f"Unexpected account url: {url=}")
    response = httpx.get(url, timeout=3)
    response.raise_for_status()
    return response.json()["nickname"]


class WebhookView(BaseBitbucketIntegrationView):
    def post(self, request):
        webhook_event = WebhookEvent.from_json_dict(request.data)
        try:
            run_handler(webhook_event)
        except HookHandleFailure as error:
            _logger.warning(str(error), exc_info=True)
            # for now we don't want to break stuff in the caller (webhooks service)
            return Response(status=200)
        return Response(status=201)


class PullRequestView(BaseBitbucketIntegrationView):
    def get(self, request, customer_id: str, repo_id: str, pr_number: int):
        store = BitbucketRepoDataStore(customer_id=customer_id, repo_id=repo_id)
        pr_data = store.get_pull_request_data(str(pr_number))
        if pr_data is None:
            raise Http404
        return Response({"pull_request_data": pr_data})


class PushView(BaseBitbucketIntegrationView):
    def get(self, request, customer_id: str, repo_id: str, ref_type: str, ref_name: str, commit_sha: str):
        store = BitbucketRepoDataStore(customer_id=customer_id, repo_id=repo_id)
        push_data = store.get_push_data(push_type=ref_type, ref_name=ref_name, commit_sha=commit_sha)
        if push_data is None:
            raise Http404
        change = push_data["push"]["changes"][0]
        return Response({"change": change, "actor": push_data["actor"]})
