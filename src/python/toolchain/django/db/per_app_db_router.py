# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import abc


class PerAppDBRouter(abc.ABC):
    """A base class for routing model queries for an entire app (or set of apps) to a specific db.

    This makes it easy to enforce a partitioning of apps across multiple databases.
    """

    def __init__(self, service_name: str, app_labels_to_route: set[str]) -> None:
        self._app_labels_to_route = frozenset(app_labels_to_route)

    @staticmethod
    def is_toolshed_admin_service(service_name: str) -> bool:
        return service_name == "toolshed"

    @property
    def app_labels_to_route(self) -> frozenset[str]:
        return self._app_labels_to_route

    @property
    @abc.abstractmethod
    def db_to_route_to(self) -> str:
        """The key of the db we route to.

        Subclasses must override.
        """

    # Subclasses may override this.

    with_content_types = True
    """Whether to non-exclusively migrate the contenttypes app onto this db.

    Subclasses may override.

    Note that this router expresses no opinion on the default db for reading or writing ContentType instances. App code
    that uses ContentType will have to set a db explicitly, or rely on the fallback to the 'default' db.
    """

    _contenttypes_app_label = "contenttypes"

    def belongs_in_db(self, model_or_obj):
        return model_or_obj._meta.app_label in self.app_labels_to_route

    def db_for_read(self, model, **hints):
        if self.belongs_in_db(model):
            return self.db_to_route_to
        # We have no opinion about other apps.
        return None

    def db_for_write(self, model, **hints):
        if self.belongs_in_db(model):
            return self.db_to_route_to
        # We have no opinion about other apps.
        return None

    def allow_relation(self, obj1, obj2, **hints) -> bool | None:
        """Whether a foreign key relation between obj1 to obj2 is allowed.

        Defaults to the Django default of only allowing relations between objects in the same db. Subclasses may
        override to change this behavior.
        """
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints) -> bool | None:
        # Models in our apps are created exclusively in our db.
        if app_label in self.app_labels_to_route:
            return db == self.db_to_route_to
        # Models for the contenttype app may be (non-exclusively) created on our db, but no
        # other app's models may be.
        elif db == self.db_to_route_to:
            return self.with_content_types and app_label == self._contenttypes_app_label
        # We have no opinion about other apps on other dbs.
        return None
