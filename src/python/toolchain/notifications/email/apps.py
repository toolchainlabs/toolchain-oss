# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.apps import AppConfig


class EmailAppConfig(AppConfig):
    name = "toolchain.notifications.email"
    label = "email_notifications"
    verbose_name = "Email dispatch app"
