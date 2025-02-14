# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.apps import AppConfig


class PantsDepgraphDemoApp(AppConfig):
    name = "toolchain.pants_demos.depgraph"
    label = "pants_demos_depgraph"
    verbose_name = "Pants Depgragh Demo App"
