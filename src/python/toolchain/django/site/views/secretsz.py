# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.http import JsonResponse
from django.views import View

from toolchain.util.secret.secrets_accessor import TrackingSecretsReader


class Secretsz(View):
    view_type = "checks"

    def get(self, _):
        return JsonResponse({"loaded": TrackingSecretsReader.get_tracked_secrets()})
