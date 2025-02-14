# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.apps import AppConfig


class AmberfloIntegrationApp(AppConfig):
    name = "toolchain.payments.amberflo_integration"
    label = "amberflo_integration"
    verbose_name = "Amberflo Integration App"
