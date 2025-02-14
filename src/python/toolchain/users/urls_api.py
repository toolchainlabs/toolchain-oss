# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.urls import include, path
from rest_framework_nested import routers

from toolchain.users import views_api, views_api_internal
from toolchain.users.jwt.views import (
    AccessTokenAuthView,
    AccessTokenExchangeView,
    AccessTokenRefreshView,
    RestrictedAccessTokenView,
)
from toolchain.users.url_names import URLNames

router = routers.SimpleRouter()
router.register("users", views_api.ToolchainUserViewSet, basename="users")
router.register("tokens", views_api.AllocatedTokensView, basename="tokens")
customer_router = routers.NestedSimpleRouter(router, "users", lookup="user")
customer_router.register("customers", views_api.CustomerViewSet, basename="customers")

new_customer_urls = [
    # We are moving away from the customer & repo router. so new urls will be added here until we can remove the old ones.
    path("customers/<slug:customer_slug>/", views_api.CustomerView.as_view(), name="customer-view"),
    path("customers/<slug:customer_slug>/plan/", views_api.CustomerPlanView.as_view(), name="customer-plan-view"),
    path(
        "customers/<slug:customer_slug>/repos/<slug:repo_slug>/",
        views_api.CustomerRepoView.as_view(),
        name="customer-repo-view",
    ),
    path(
        "customers/<slug:customer_slug>/billing/",
        views_api.CustomerBillingView.as_view(),
        name=URLNames.CUSTOMER_BILLING,
    ),
    path(
        "customers/<slug:customer_slug>/workers/tokens/",
        views_api.CustomerRemoteWorkerTokensView.as_view(),
        name="customer-worker-tokens-view",
    ),
    path(
        "customers/<slug:customer_slug>/workers/tokens/<str:token_id>/",
        views_api.CustomerRemoteWorkerTokenView.as_view(),
        name="customer-worker-token-view",
    ),
]


jwt_views_urls = [
    path("token/auth/", AccessTokenAuthView.as_view(), name="auth-for-token"),
    path("token/exchange/", AccessTokenExchangeView.as_view(), name="auth-token-exchange"),
    path("token/refresh/", AccessTokenRefreshView.as_view(), name="auth-token-refresh"),
    path("token/restricted/", RestrictedAccessTokenView.as_view(), name="auth-token-restricted"),
]
internal_api_urls = [
    path("customers/<customer_pk>/users/resolve/", views_api_internal.ResolveUserView.as_view()),
    path("customers/<customer_pk>/users/admin/", views_api_internal.AdminUsersView.as_view()),
]

urlpatterns = [
    path(
        "api/v1/",
        include(jwt_views_urls + router.urls + customer_router.urls + new_customer_urls),
    ),
    path("internal/api/v1/", include(internal_api_urls)),
]
