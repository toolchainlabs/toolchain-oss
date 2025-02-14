# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.urls import path

from toolchain.users.ui.url_names import URLNames
from toolchain.users.ui.views import (
    InstallGithubAppView,
    NoOrgView,
    ToolchainLoginView,
    ToolchainLogoutView,
    UserAccessDeniedView,
    UserTOSView,
    bitbucket_auth,
    bitbucket_complete,
    github_auth,
    github_complete,
    impersonate,
)

urlpatterns = [
    path("auth/login/github/", github_auth, name=URLNames.GITHUB_AUTH_BEGIN),
    path("auth/complete/github/", github_complete, name=URLNames.GITHUB_AUTH_COMPLETE),
    path("auth/login/bitbucket/", bitbucket_auth, name=URLNames.BITBUCKET_AUTH_BEGIN),
    path("auth/complete/bitbucket/", bitbucket_complete, name=URLNames.BITBUCKET_AUTH_COMPLETE),
    # Customize some auth view setup.
    path("auth/login/", ToolchainLoginView.as_view(), name="login"),
    path("auth/logout/", ToolchainLogoutView.as_view(), name="logout"),
    path("auth/denied/", UserAccessDeniedView.as_view(), name=URLNames.USER_ACCESS_DENIED),
    path("tos/", UserTOSView.as_view(), name=URLNames.TOS),
    path("org/install/", InstallGithubAppView.as_view(), name=URLNames.GITHUB_APP_INSTALL),
    path("org/", NoOrgView.as_view(), name=URLNames.NO_ORG),
    path("impersonate/start/<str:session_id>/", impersonate, name=URLNames.IMPERSONATE_START),
    path("impersonate/end/", ToolchainLogoutView.as_view(), name=URLNames.IMPERSONATE_END),
]
