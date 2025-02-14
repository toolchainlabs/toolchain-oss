# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import logging

import stripe
from django.conf import settings
from django.http import Http404
from rest_framework.views import APIView, Response

from toolchain.payments.stripe_integration.handlers import handle_event
from toolchain.payments.stripe_integration.models import SubscribedCustomer
from toolchain.payments.stripe_integration.stripe_client import StripeCustomersClient

_logger = logging.getLogger(__name__)


class StripeCustomerPortalView(APIView):
    def post(self, request, customer_pk: str):
        # internal API, if return URL is missing there is a bug in our code. so we might as well crash here.
        return_url = request.POST["return-url"]
        client = StripeCustomersClient(toolchain_env_name=settings.TOOLCHAIN_ENV.get_env_name())
        sc = SubscribedCustomer.get_by_customer_id(customer_id=customer_pk)
        if not sc:
            _logger.warning(f"no SubscribedCustomer for {customer_pk=}")
            raise Http404

        session_url = client.create_customer_portal_session(
            stripe_customer_id=sc.stripe_customer_id, return_url=return_url
        )
        return Response(
            status=201,
            data={
                "session_url": session_url,
                "stripe_customer_id": sc.stripe_customer_id,
            },
        )


class StripeProcessWebhookView(APIView):
    def post(self, request):
        event = stripe.Event.construct_from(json.loads(request.body), stripe.api_key)
        _logger.info(f"Got Stripe event: {event.type} stripe_id={event.stripe_id}")
        handled = handle_event(event)
        return Response(status=201 if handled else 200)
