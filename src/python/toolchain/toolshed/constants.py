# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Order matters here, ToolshedAdminAppConfig needs to be before django.contrib.admin in order to be
# able to override templates.

from toolchain.bitbucket_integration.constants import BITBUCKET_INTEGRATION_DJANGO_APP
from toolchain.github_integration.constants import GITHUB_INTEGRATION_DJANGO_APP
from toolchain.users.constants import USERS_DB_DJANGO_APPS

ADMIN_APPS = USERS_DB_DJANGO_APPS + (
    "django.contrib.sessions",
    "django.contrib.messages",
    "toolchain.toolshed.apps.ToolshedAdminAppConfig",
    "django.contrib.admin",
    "toolchain.buildsense.ingestion.apps.BuildDataIngestionAppConfig",
    "toolchain.workflow.apps.WorkflowAppConfig",
    BITBUCKET_INTEGRATION_DJANGO_APP,
    GITHUB_INTEGRATION_DJANGO_APP,
    "toolchain.oss_metrics.bugout_integration.apps.BugoutIntegrationAppConfig",
    "toolchain.oss_metrics.apps.OssMetricsAppConfig",
    "toolchain.pants_demos.depgraph.apps.PantsDepgraphDemoApp",
    "toolchain.payments.stripe_integration.apps.StripeIntegrationApp",
    "toolchain.payments.amberflo_integration.apps.AmberfloIntegrationApp",
)

DEV_ONLY_ADMIN_APPS = ("toolchain.notifications.email.apps.EmailAppConfig",)

ADMIN_DBS = (
    "users",
    "buildsense",
    "scm_integration",
    "oss_metrics",
    "pants_demos",
    "payments",
)

DEV_ONLY_ADMIN_DBS = ("notifications",)


TOOLSHED_MIDDLEWARE = (
    "toolchain.toolshed.middleware.AdminDbContextMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "social_django.middleware.SocialAuthExceptionMiddleware",
    "toolchain.toolshed.middleware.AuthMiddleware",
)

DJANGO_TEMPLATE_CONFIG = {
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "OPTIONS": {
        "context_processors": [
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
            "django.template.context_processors.request",
        ],
        "loaders": [
            # NB: The cached.Loader doesn't cache when DEBUG=True.
            # NB: The DjangoPackageLoader will load from the filesystem when running directly from
            # sources during development, but it won't reload templates on file changes, which is a crucial
            # feature when developing. so we try an app_directories.Loader first.
            (
                "django.template.loaders.cached.Loader",
                [
                    "toolchain.django.resources.template_loaders.DjangoPackageLoader",
                    "django.template.loaders.app_directories.Loader",
                ],
            )
        ],
    },
}


AUTH_PIPLINE = (
    "social_core.pipeline.social_auth.social_details",
    "toolchain.toolshed.auth_util.check_toolchain_access",
    "social_core.pipeline.social_auth.social_uid",
    "social_core.pipeline.social_auth.auth_allowed",
)
