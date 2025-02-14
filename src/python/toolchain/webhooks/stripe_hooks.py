# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

import stripe
from django.conf import settings
from django.http import HttpResponse
from django.views.generic import View

from toolchain.payments.stripe_integration.client.webhook_client import StripeWebhooksClient

_logger = logging.getLogger(__name__)


class StripeWebhookView(View):
    view_type = "app"
    # Loading it here so we crash on startup if the setting doesn't exist for some reason.
    ENDPOINT_SECRET = settings.STRIPE_WEBHOOK_ENDPOINT_SECRET

    def _reject_webhook(self, reason: str, error_details: str):
        _logger.warning(f"reject_stripe_webhook {reason=} {error_details}")
        return HttpResponse()

    def post(self, request):
        # https://stripe.com/docs/webhooks#webhook-endpoint-three
        sig_header = request.headers.get("Stripe-Signature")
        content_type = request.headers.get("Content-Type", "")
        if not content_type.startswith("application/json"):
            return self._reject_webhook("invalid content type", content_type)
        payload = request.body
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, self.ENDPOINT_SECRET)
        except ValueError as err:
            return self._reject_webhook(reason="invalid_payload", error_details=repr(err))
        except stripe.error.SignatureVerificationError as err:
            return self._reject_webhook(reason="invalid_signature", error_details=repr(err))
        _logger.info(f"Got Stripe webhook: {event.type} stripe_id={event.stripe_id}")
        StripeWebhooksClient.for_settings(settings).post_webhook(event)
        return HttpResponse()
