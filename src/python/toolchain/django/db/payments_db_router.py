# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.django.db.per_app_db_router import PerAppDBRouter


class PaymentsDBRouter(PerAppDBRouter):
    db_to_route_to = "payments"

    def __init__(self, service_name: str) -> None:
        app_labels = {"amberflo_integration", "stripe_integration", "workflow"}
        super().__init__(service_name, app_labels)
