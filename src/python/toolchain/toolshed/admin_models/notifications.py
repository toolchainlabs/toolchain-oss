# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from toolchain.notifications.email.models import EmailMessageRequest, ProcessEmailMessageRequest, SentEmailMessage
from toolchain.toolshed.admin_models.utils import ReadOnlyModelAdmin


def get_notifications_models():
    return {
        EmailMessageRequest: ReadOnlyModelAdmin,
        SentEmailMessage: ReadOnlyModelAdmin,
        ProcessEmailMessageRequest: ReadOnlyModelAdmin,
    }
