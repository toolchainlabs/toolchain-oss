# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.urls import include, path, re_path

from toolchain.bitbucket_integration.api.views import AppInstallView, PullRequestView, PushView, WebhookView

customer_repo_patterns = [
    path("pull_requests/<int:pr_number>/", PullRequestView.as_view()),
    re_path(r"push/(?P<ref_type>[a-z]+)/(?P<ref_name>[\w\d/\.\_\-]+)/(?P<commit_sha>[a-f0-9]+)/", PushView.as_view()),
]

bitbucket_url_patterns = [
    path("app/install/", AppInstallView.as_view()),
    path("webhook/", WebhookView.as_view()),
    path("<customer_id>/<repo_id>/", include(customer_repo_patterns)),
]
