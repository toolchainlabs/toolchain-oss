# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from django.urls import reverse

from toolchain.pants_demos.depgraph.models import DemoRepo
from toolchain.pants_demos.depgraph.url_names import URLNames


def get_url_for_repo(dr: DemoRepo) -> str:
    return reverse(URLNames.REPO_VIEW, kwargs={"account": dr.repo_account, "repo": dr.repo_name})
