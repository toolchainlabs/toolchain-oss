# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.django.db.per_app_db_router import PerAppDBRouter


class NotificationsDBRouter(PerAppDBRouter):
    db_to_route_to = "notifications"

    def __init__(self, service_name: str) -> None:
        app_labels = {"email_notifications", "workflow"}
        super().__init__(service_name, app_labels)
