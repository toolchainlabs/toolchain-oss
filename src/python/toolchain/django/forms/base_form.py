# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.forms import Form, ValidationError


class ToolchainForm(Form):
    allow_unexpected_fields: bool = False

    def clean(self):
        cleaned = super().clean()
        unexpected_fields = set(self.data.keys() - set(self.fields.keys()))
        if unexpected_fields and not self.allow_unexpected_fields:
            unexpected_fields_str = ", ".join(sorted(unexpected_fields))
            raise ValidationError(f"Got unexpected fields: {unexpected_fields_str}", code="unexpected")
        return cleaned
