# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.contrib.auth.mixins import UserPassesTestMixin

from toolchain.django.util.view_util import ToolchainAccessMixin


class SuperuserOnlyMixin(ToolchainAccessMixin, UserPassesTestMixin):
    """Subclass views will only be accessible to superusers."""

    # Subclasses must provide this as an instance property.
    request = None

    def test_func(self):
        return self.request.user.is_superuser
