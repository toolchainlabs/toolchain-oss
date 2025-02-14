# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.urls import include, path, re_path

from toolchain.github_integration.api.views import (
    AppWebhookView,
    CIResolveView,
    CommitsView,
    CustomerRepoView,
    PullRequestView,
    PushView,
    RepoWebhookView,
)

customer_repo_patterns = [
    path("pull_requests/<int:pr_number>/", PullRequestView.as_view()),
    path("ci/", CIResolveView.as_view()),
    re_path(r"commit/(?P<ref_name>[\w\d/\.\_\-]+)/(?P<commit_sha>[a-f0-9]+)/", CommitsView.as_view()),
    re_path(r"push/(?P<ref_name>[\w\d/\.\_\-]+)/(?P<commit_sha>[a-f0-9]+)/", PushView.as_view()),
]


github_url_patterns = [
    path("hooks/app/", AppWebhookView.as_view()),
    path("hooks/repos/<github_repo_id>/", RepoWebhookView.as_view()),
    path("<customer_id>/", CustomerRepoView.as_view()),
    path("<customer_id>/<repo_id>/", include(customer_repo_patterns)),
]
