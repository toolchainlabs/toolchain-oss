# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging

from django.db.models import Model
from django.http import Http404

_logger = logging.getLogger(__name__)


# See https://github.com/rocioar/flake8-django/issues/46
class ToolchainModel(Model):  # noqa: DJ08
    class Meta:
        abstract = True

    @classmethod
    def base_qs(cls):
        return cls.objects

    @classmethod
    def get_or_none(cls, **kwargs):
        qs = cls.base_qs().filter(**kwargs)
        try:
            return qs.get()
        except cls.DoesNotExist:
            return None

    @classmethod
    def get_or_404(cls, **kwargs):
        qs = cls.base_qs().filter(**kwargs)
        try:
            return qs.get()
        except cls.DoesNotExist:
            _logger.warning(f"{cls.__name__} not found with {kwargs!r}")
            raise Http404()
