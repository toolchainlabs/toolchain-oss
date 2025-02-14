# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.toolshed.admin_models.buildsense import get_buildsense_models
from toolchain.toolshed.admin_models.oss_metrics import get_oss_metrics_models
from toolchain.toolshed.admin_models.pants_demos import get_pants_demos_models
from toolchain.toolshed.admin_models.payments import get_payments_models
from toolchain.toolshed.admin_models.scm_integration import get_scm_integration_models
from toolchain.toolshed.admin_models.users import get_user_models
from toolchain.toolshed.admin_models.workflow import get_workflow_models


class AdminModelsMap:
    def __init__(self, is_dev: bool) -> None:
        self._models = {}
        self._models.update(get_user_models())
        self._models.update(get_workflow_models())
        self._models.update(get_buildsense_models())
        self._models.update(get_scm_integration_models())
        self._models.update(get_oss_metrics_models())
        self._models.update(get_pants_demos_models())
        self._models.update(get_payments_models())
        if is_dev:
            from toolchain.toolshed.admin_models.notifications import get_notifications_models

            self._models.update(get_notifications_models())

    def get_admin_class(self, model):
        return self._models.get(model)
