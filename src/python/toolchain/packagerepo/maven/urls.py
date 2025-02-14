# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.packagerepo.maven.views import get_maven_package_repo_urls

app_name = "maven"


urlpatterns = get_maven_package_repo_urls("")
