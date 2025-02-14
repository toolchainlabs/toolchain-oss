# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.http import JsonResponse
from django.views import View

from toolchain.django.site.models import check_models_read_access


class DependentResourcesCheckz(View):
    view_type = "checks"

    def get(self, _):
        return JsonResponse(data=check_models_read_access())
