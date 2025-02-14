# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.contrib.postgres.search import SearchVector
from django.db.models import F, Func, Value
from django.db.models.signals import post_save


def _update_workexception_search_vector(sender, instance, created, **kwargs):
    # We know that these fields never change, so we only need to update on creation.
    if created:
        # Note that Django doesn't allow joins in an update, so we have to use this post_save
        # annotation trick to set the search_vector to include fields from other models.
        annotated_instance = (
            sender.objects.filter(pk=instance.pk)
            .annotate(
                document=SearchVector(
                    "message",
                    Func(F("message"), Value("/"), Value(" "), function="replace"),
                    "work_unit__payload_ctype__model",
                    "work_unit__description",
                    Func(F("work_unit__description"), Value("/"), Value(" "), function="replace"),
                )
            )
            .get()
        )
        instance.search_vector = annotated_instance.document
        instance.save(update_fields=["search_vector"])


def register_signals_for_workexceptionlogs():
    # Local import, so we don't try to indirectly import models during app setup.
    from toolchain.workflow.models import WorkExceptionLog

    # We know that WorkExceptionLog instances are never bulk-created, so the signal is always triggered.
    post_save.connect(_update_workexception_search_vector, sender=WorkExceptionLog)
