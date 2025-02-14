# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.apps import AppConfig


class ServiceRouterAppConfig(AppConfig):
    name = "toolchain.servicerouter"
    label = "servicerouter"
    verbose_name = "App to serve the frontend and route requests to various backend services."
