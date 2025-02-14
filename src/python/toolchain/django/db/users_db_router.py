# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from toolchain.django.db.per_app_db_router import PerAppDBRouter


class UsersDBRouter(PerAppDBRouter):
    db_to_route_to = "users"

    def __init__(self, service_name: str) -> None:
        # When non-admin (toolshed) and non-users services are accessing the DB, they only need to access site & sessions.
        app_labels = {"sessions", "site"}
        if service_name.startswith("users/") or PerAppDBRouter.is_toolshed_admin_service(service_name):
            app_labels.update({"workflow", "admin", "auth", "users"})
        # TECH DEBT: This is only needed until servicerouter calls the users api to check impersonation sessions #10115
        if service_name == "servicerouter":
            app_labels.add("users")
        super().__init__(service_name, app_labels)

    def allow_relation(self, obj1, obj2, **hints) -> bool | None:
        # Allow relations across databases if a model in one of our apps is involved.
        # This allows us to have "foreign keys" to the User model in our various models.
        # They won't be enforced as actual database foreign keys, of course, but Django
        # will still be able to traverse them, at the cost of another db roundtrip.
        # We'll probably never need this ability for the admin or sessions apps, as there's
        # nothing in those that we'll likely ever want to reference via foreign key. But we
        # might as well be consistent.
        if self.belongs_in_db(obj1) or self.belongs_in_db(obj2):
            return True
        return None
