# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest
from django.core.exceptions import ValidationError

from toolchain.django.site.utils import validators


def test_validate_noslash() -> None:
    validators.validate_noslash("I do not have a slash")
    with pytest.raises(ValidationError):
        validators.validate_noslash("I /do/ have a slash")


def test_validate_nopipe() -> None:
    validators.validate_nopipe("I do not have a pipe")
    with pytest.raises(ValidationError):
        validators.validate_nopipe("I |do| have a slash")
