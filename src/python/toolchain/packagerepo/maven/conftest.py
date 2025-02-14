# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.conftest import APPS_UNDER_TEST

APPS_UNDER_TEST.extend(
    [
        "toolchain.packagerepo.maven.apps.PackageRepoMavenAppConfig",
        "toolchain.django.webresource.apps.WebResourceAppConfig",
    ]
)
