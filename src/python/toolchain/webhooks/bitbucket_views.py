# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import logging
from copy import deepcopy

import pkg_resources
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.views.generic import View

from toolchain.bitbucket_integration.client.app_clients import AppClient
from toolchain.bitbucket_integration.common.events import (
    AppInstallEvent,
    AppUninstallEvent,
    InvaliBitBucketEvent,
    WebhookEvent,
    read_jwt,
)
from toolchain.webhooks.constants import URLNames

_logger = logging.getLogger(__name__)


def load_descriptor(name: str) -> dict:
    return json.loads(pkg_resources.resource_string(__name__, f"descriptors/{name}.json"))


class BitBucketAppDescriptorView(View):
    view_type = "app"
    _DESCRIPTOR_DATA = load_descriptor("bitbucket-app")

    def _get_descriptor(self) -> dict:
        # https://developer.atlassian.com/cloud/bitbucket/app-descriptor/
        descriptor = deepcopy(self._DESCRIPTOR_DATA)
        app_descriptor = settings.BITBUCKET_APP
        host = settings.WEBHOOKS_HOST

        descriptor["modules"]["webhooks"][0]["url"] = reverse(URLNames.BITBUCKET_WEBHOOK)
        descriptor["lifecycle"].update(
            installed=reverse(URLNames.BITBUCKET_APP_INSTALL), uninstalled=reverse(URLNames.BITBUCKET_APP_UNINSTALL)
        )

        descriptor.update(
            # Must be https, bitbucket doesn't like it when it is http.
            # Trailing slash also breaks bitbucket.
            baseUrl=f"https://{host}",
            key=app_descriptor.key,
            name=app_descriptor.name,
            description=app_descriptor.description,
        )
        return descriptor

    def get(self, request):
        return JsonResponse(data=self._get_descriptor())


class BaseHookView(View):
    def _reject(self, name: str, reason: str, error: str = "") -> HttpResponse:
        _logger.warning(f"reject_bitbucket webhook={name} {reason=} {error}")
        # TODO: Add a metric/counter
        # TODO: block IP that gives us bad data for a while.
        return HttpResponse("OK")  # Don't let caller know the call is bad.


class BitBucketAppWebhookView(BaseHookView):
    def post(self, request) -> HttpResponse:
        client = AppClient.for_settings(settings)
        webhook_event = WebhookEvent.create(headers=request.headers, body=request.body)
        client.send_webhook(webhook_event)
        return HttpResponse("OK")


class BitBucketAppInstallView(BaseHookView):
    def post(self, request):
        # https://developer.atlassian.com/cloud/bitbucket/authentication-for-apps/
        client = AppClient.for_settings(settings)
        payload = json.loads(request.body)
        try:
            jwt_str = read_jwt(request.headers)
        except InvaliBitBucketEvent as err:
            return self._reject("app_install", "jwt_error", error=str(err))
        install_event = AppInstallEvent.from_payload(jwt=jwt_str, json_payload=payload)
        client.app_install(app_install=install_event)
        return HttpResponse("OK")


class BitBucketAppUninstallView(BaseHookView):
    def post(self, request):
        # https://developer.atlassian.com/cloud/bitbucket/authentication-for-apps/
        client = AppClient.for_settings(settings)
        payload = json.loads(request.body)
        try:
            jwt_str = read_jwt(request.headers)
        except InvaliBitBucketEvent as err:
            return self._reject("app_uninstall", "jwt_error", error=str(err))
        uninstall_event = AppUninstallEvent.from_payload(jwt=jwt_str, json_payload=payload)
        client.app_uninstall(app_uninstall=uninstall_event)
        return HttpResponse("OK")
