# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.packagerepo.pypi.views import get_pypi_package_repo_urls

app_name = "pypi"


urlpatterns = get_pypi_package_repo_urls("")
