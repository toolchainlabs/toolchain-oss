# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.apps import apps

from toolchain.toolshed.admin_models.loader import AdminModelsMap


def test_missing_admin_models():
    """This test makes sure that we have an admin model (or that we explicitly choose not to have one) for all first
    party models.

    This is critical since if we don't have an admin model for a given model it means we don't reference that model from
    toolshed. Not referencing the a model from toolshed causes it to not be a part of the deployment PEX which will
    cause issues with migrations and with content type creation for that model.
    """
    models_map = AdminModelsMap(is_dev=True)
    missing_models = []
    for model in apps.get_models():
        if not model.__module__.startswith("toolchain."):
            continue
        admin_model = models_map.get_admin_class(model)
        if admin_model is None:
            missing_models.append(model)
    assert not missing_models
