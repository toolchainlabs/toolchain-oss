# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.db.models import IntegerField, Model


class Number(Model):
    """Dummy model used for testing."""

    class Meta:
        pass

    value = IntegerField(db_index=True, unique=True)

    def __str__(self):
        return "Test-Number-Model"
