# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.core.wsgi import get_wsgi_application

# A generic WSGI entrypoint for all our services, Used by gunicorn in production (or dev in k8s).

# Use the standard Django WSGI handler.
application = get_wsgi_application()
