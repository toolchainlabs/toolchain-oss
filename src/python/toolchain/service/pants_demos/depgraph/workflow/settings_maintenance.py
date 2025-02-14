# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.django.site.settings.service import *  # noqa: F403
from toolchain.workflow.settings_extra_maintenance import *  # noqa: F403

INSTALLED_APPS.append("toolchain.pants_demos.depgraph.apps.PantsDepgraphDemoApp")

set_up_databases(__name__, "pants_demos")
