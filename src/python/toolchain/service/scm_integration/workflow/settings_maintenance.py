# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.django.site.settings.service import *  # noqa: F403
from toolchain.github_integration.constants import GITHUB_INTEGRATION_DJANGO_APP
from toolchain.workflow.settings_extra_maintenance import *  # noqa: F403

INSTALLED_APPS.append(GITHUB_INTEGRATION_DJANGO_APP)

set_up_databases(__name__, "scm_integration")
