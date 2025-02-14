# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.http import HttpResponse
from django.views import View


# The healthz view lives in its own file so that it can be imported without bringing in
# dependencies on auth, contenttypes etc. and therefore can be used in apps with no database.
class Healthz(View):
    view_type = "checks"

    def get(self, _):
        return HttpResponse("OK")
