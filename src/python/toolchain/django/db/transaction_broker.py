# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from functools import cached_property

from django.contrib.contenttypes.models import ContentType
from django.db import connections, transaction

from toolchain.django.db.db_router_registry import DBRouterRegistry


class TransactionBroker:
    def __init__(self, app_label):
        self._app_label = app_label

    @cached_property
    def db_name(self):
        # NB: Must be computed lazily, since we create TransactionBroker instances as module globals,
        # and the DBRouterRegistry might not be set up yet.
        return DBRouterRegistry.get_db_name_for_app(self._app_label)

    @property
    def content_type_mgr(self):
        """Return a manager for ContentTypes stored on the db we transact on."""
        return ContentType.objects.db_manager(self.db_name)

    @property
    def connection(self):
        """Return a raw connection to the db we transact on."""
        return connections[self.db_name]

    def atomic(self, using=None, savepoint=True):
        """A transaction context for the app."""
        if callable(using):
            # Bare decorator: @atomic. Although the first argument is called `using`, in the bare decorator case
            # it's actually the function being decorated.  This is for uniformity with the underlying Django
            # atomic() method. See that method's implementation for more.
            return transaction.atomic(using, savepoint)
        elif using is not None:
            raise ValueError(f"Must not specify value for using= in a brokered transaction for db {self.db_name}.")
        else:
            # Decorator: @atomic(...) or context manager: with atomic(...): ...
            return transaction.atomic(using=self.db_name, savepoint=savepoint)
