# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.django.db.per_app_db_router import PerAppDBRouter


class BuildSenseDBRouter(PerAppDBRouter):
    db_to_route_to = "buildsense"

    def __init__(self, service_name: str) -> None:
        super().__init__(service_name, {"workflow", "buildsense", "ingestion"})
