# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Based on https://github.com/jdelic/django-postgresql-setrole/
# The reason we forked it is that the original repo hard codes the sender type, when we use
# django Prometheus DB integration, this type changes since it gets wrapped by
# django_prometheus.db.backends.postgresql.base.DatabaseWrapper


from django.apps import AppConfig
from django.db.backends.signals import connection_created


def setrole_connection(*, sender, connection, **kwargs):
    if "SET_ROLE" not in connection.settings_dict:
        return
    role = connection.settings_dict["SET_ROLE"]
    connection.cursor().execute("SET ROLE %s", (role,))


class DjangoPostgreSQLSetRoleApp(AppConfig):
    name = __name__

    def ready(self):
        connection_created.connect(setrole_connection)
