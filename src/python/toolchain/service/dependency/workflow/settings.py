# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.django.site.settings.service import *  # noqa: F403
from toolchain.workflow.settings_extra_worker import *  # noqa: F403

INSTALLED_APPS.append("toolchain.dependency.apps.DependencyAPIAppConfig")

set_up_databases(__name__, "dependency")

# TODO: handle non-k8s use cases.
DEPGRAPH_BASE_DIR_URL = config["DEPGRAPH_BASE_DIR_URL"]
LOCAL_DEPGRAPH_DIR_URL = config["LOCAL_DEPGRAPH_DIR_URL"]
# Temporary setting while we test the async resolver side by side with the sync resolver.
DRY_RUN_WORKFLOW_RESOLVE = False
