# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.django.site.settings.util import MiddlewareAuthMode, get_middleware

BUILDSENSE_API_MIDDLEWARE = get_middleware(auth_mode=MiddlewareAuthMode.INTERNAL, with_csp=False)
