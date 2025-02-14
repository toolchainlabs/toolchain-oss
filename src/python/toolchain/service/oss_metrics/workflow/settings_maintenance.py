# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.django.site.settings.service import *  # noqa: F403
from toolchain.workflow.settings_extra_maintenance import *  # noqa: F403

INSTALLED_APPS.extend(
    (
        "toolchain.oss_metrics.bugout_integration.apps.BugoutIntegrationAppConfig",
        "toolchain.oss_metrics.apps.OssMetricsAppConfig",
    )
)

set_up_databases(__name__, "oss_metrics")
