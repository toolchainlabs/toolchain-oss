# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.http import JsonResponse
from django.views import View

from toolchain.github_integration.models import check_models_read_access
from toolchain.github_integration.repo_data_store import GithubRepoDataStore


class ResourcesCheckz(View):
    view_type = "checks"

    def get(self, _):
        s3_check = GithubRepoDataStore.check_access()
        db_check = check_models_read_access()
        access_results = {
            "db": db_check,
            "s3": s3_check,
        }
        return JsonResponse(data=access_results)
