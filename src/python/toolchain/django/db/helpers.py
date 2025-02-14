# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.db.transaction_broker import TransactionBroker

_logger = logging.getLogger(__name__)


def create_or_update_singleton(cls, transaction: TransactionBroker, **kwargs):
    name = cls.__name__
    if cls.objects.count() > 1:
        raise ToolchainAssertion(f"More than one {name} detected. This is not supported currently.")
    with transaction.atomic():
        obj = cls.objects.first()
        if obj:
            curr_values = {getattr(obj, key) for key in kwargs}
            _logger.info(f"Update {name} from={curr_values} to {kwargs}")
            for key, value in kwargs.items():
                setattr(obj, key, value)
            obj.save()

        else:
            _logger.info(f"Create {name} with {kwargs}")
            obj = cls.objects.create(**kwargs)
        return obj
