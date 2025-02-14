# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.core.exceptions import ValidationError


# Note that validators are not defined in models.py because migrations need access to them,
# and importing models in migrations is iffy (not to mention confusing) due to metaclass magic.
def validate_noslash(value):
    """Validates that a field does not contain the (forward) slash character.

    Typically used for fields that might be used as slugs in URLs.
    """
    if "/" in value:
        raise ValidationError("Value must not contain the forward slash character")


def validate_nopipe(value):
    """Validates that a field does not contain the pipe character."""
    if "|" in value:
        raise ValidationError("Value must not contain the pipe character")
