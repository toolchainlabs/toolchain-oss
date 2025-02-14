# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.django.db.per_app_db_router import PerAppDBRouter


class PyPiDBRouter(PerAppDBRouter):
    db_to_route_to = "pypi"

    def __init__(self, service_name: str) -> None:
        app_labels = {"webresource", "packagerepopypi"}
        #  Workflow related models are only accessed in crawler, not in dependency api
        if service_name.startswith("crawler/pypi") or self.is_toolshed_admin_service(service_name):
            app_labels.update({"workflow", "crawlerbase", "crawlerpypi"})
        super().__init__(service_name, app_labels)
