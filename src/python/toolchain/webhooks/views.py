# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from csp.decorators import csp_exempt
from django.http.response import HttpResponsePermanentRedirect


@csp_exempt
def home_page(request):
    return HttpResponsePermanentRedirect(redirect_to="https://toolchain.com")
