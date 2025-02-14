# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.urls import include, path

from toolchain.django.site.views.urls_api_base import api_urlpatterns_base
from toolchain.payments.api.internal_views_api import InternalPaymentsCustomerViewView
from toolchain.payments.stripe_integration.internal_views_api import StripeCustomerPortalView, StripeProcessWebhookView

internal_api_urls = [
    path("webhooks/", StripeProcessWebhookView.as_view()),
    path("customers/<customer_pk>/portal/", StripeCustomerPortalView.as_view()),
    path("customers/<customer_pk>/info/", InternalPaymentsCustomerViewView.as_view()),
]

urlpatterns = api_urlpatterns_base() + [
    path("internal/api/v1/", include(internal_api_urls)),
]
