# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.urls import path

from toolchain.django.site.views.urls_base import urlpatterns_base
from toolchain.django.site.views.well_known import get_robots_txt_url
from toolchain.webhooks.aws_ses_hooks import AwsSesWebhookView
from toolchain.webhooks.bitbucket_views import (
    BitBucketAppDescriptorView,
    BitBucketAppInstallView,
    BitBucketAppUninstallView,
    BitBucketAppWebhookView,
)
from toolchain.webhooks.constants import URLNames
from toolchain.webhooks.github_hooks import GithubAppWebhookView, GithubRepoWebhookView
from toolchain.webhooks.stripe_hooks import StripeWebhookView
from toolchain.webhooks.views import home_page

_github_patterns = [
    path("github/app/", GithubAppWebhookView.as_view(), name="github-app-webhook"),
    path("github/repo/", GithubRepoWebhookView.as_view(), name="github-repo-webhook"),
]


_bitbucket_patterns = [
    path("bitbucket/descriptor/", BitBucketAppDescriptorView.as_view(), name="bitbucket-descriptor"),
    path("bitbucket/app/install/", BitBucketAppInstallView.as_view(), name=URLNames.BITBUCKET_APP_INSTALL),
    path("bitbucket/app/uninstall/", BitBucketAppUninstallView.as_view(), name=URLNames.BITBUCKET_APP_UNINSTALL),
    path("bitbucket/webhook/", BitBucketAppWebhookView.as_view(), name=URLNames.BITBUCKET_WEBHOOK),
]
urlpatterns = (
    urlpatterns_base()
    + _bitbucket_patterns
    + _github_patterns
    + [
        path("stripe/", StripeWebhookView.as_view(), name="stripe-webhook"),
        path("aws/ses/", AwsSesWebhookView.as_view(), name="aws-ses-webhook"),
        get_robots_txt_url(allow_indexing=False),
        path("", home_page, name="home"),
    ]
)
