# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import textwrap
from collections import OrderedDict

from django.conf import settings
from django.db import Error as DBError
from django.db import connections
from django.urls import path, reverse
from django.views.generic import TemplateView

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.util.view_util import AjaxView
from toolchain.toolshed.admin_db_context import get_db_context
from toolchain.toolshed.util.view_util import SuperuserOnlyMixin


class DbzDataViewMixin:
    view_type = "checks"
    _POSTGRES_ENGINES = {"django.db.backends.postgresql", "django_prometheus.db.backends.postgresql"}

    @property
    def db(self):
        return get_db_context()

    @property
    def connection(self):
        try:
            db_connection = connections[self.db]
        except KeyError:
            raise ToolchainAssertion(f"Unknown database: {self.db}")
        if db_connection.settings_dict["ENGINE"] not in self._POSTGRES_ENGINES:
            raise NotImplementedError("View only implemented for PostgreSQL.")
        return db_connection


class DbzTemplateView(SuperuserOnlyMixin, TemplateView):
    _VIEW_NAMES = [
        "dbz_backends",
        "dbz_backends_data",
        "dbz_bgwriter",
        "dbz_locks",
        "dbz_locks_data",
        "dbz_blocked_locks",
        "dbz_blocked_locks_data",
        "dbz_explain",
        "dbz_explain_data",
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        db_name = get_db_context()
        context["views_links"] = {view_name: reverse(f"{view_name}-{db_name}") for view_name in self._VIEW_NAMES}
        return context


class Dbz(DbzTemplateView):
    template_name = "pgstats/dbz.html"


class DbzBackends(DbzTemplateView):
    template_name = "pgstats/dbz_backends.html"


class DbzLocks(DbzTemplateView):
    template_name = "pgstats/dbz_locks.html"


class DbzBlockedLocks(DbzTemplateView):
    template_name = "pgstats/dbz_blocked_locks.html"


class DbzBgWriter(DbzTemplateView, DbzDataViewMixin):
    template_name = "pgstats/dbz_bgwriter.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["bgwriter_stats"] = self.get_bgwriter_stats()
        return context

    def get_bgwriter_stats(self):
        with self.connection.cursor() as cursor:
            cursor.execute(textwrap.dedent("SELECT * FROM pg_stat_bgwriter"))
            columns = [col[0] for col in cursor.description]
            return OrderedDict(zip(columns, cursor.fetchall()[0]))


class DbzExplain(DbzTemplateView):
    template_name = "pgstats/dbz_explain.html"


class DbzDataView(SuperuserOnlyMixin, DbzDataViewMixin, AjaxView):
    pass


class DbzBackendsData(DbzDataView):
    returns_list = True

    def get_ajax_data(self):
        username = self.request.GET.get("u")
        if username == "me":
            username = settings.DATABASES["users"]["USER"]

        with self.connection.cursor() as cursor:
            # Note that 'usename' in the SQL is not a typo.
            if username:
                cursor.execute("SELECT * FROM pg_stat_activity where usename=%s", [username])
            else:
                cursor.execute("SELECT * FROM pg_stat_activity")
            rows = _results_dicts(cursor)
            for row in rows:
                addr = row["client_addr"]
                port = row["client_port"]
                row["client"] = f"{addr}:{port}" if addr else ""
            return rows


class DbzLocksData(DbzDataView):
    returns_list = True

    def get_ajax_data(self):
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            current_db_name = cursor.fetchall()[0][0]

            cursor.execute(
                textwrap.dedent(
                    """
                    SELECT pid, datname, locktype, relname, mode, granted
                    FROM pg_locks as pl
                    LEFT JOIN pg_database as pd ON pl.database = pd.oid
                    LEFT JOIN pg_class as pc ON pl.relation = pc.oid
                    """
                )
            )
            ret = _results_dicts(cursor)
            for row in ret:
                # The relname computed by the join is correct only if we're on the current db (or no db).
                # See https://www.postgresql.org/docs/9.6/static/view-pg-locks.html.
                if row["datname"] and row["datname"] != current_db_name:
                    row["relname"] = ""
            return ret


class DbzBlockedLocksData(DbzDataView):
    returns_list = True

    def get_ajax_data(self):
        with self.connection.cursor() as cursor:
            # See https://wiki.postgresql.org/wiki/Lock_Monitoring.
            cursor.execute(
                textwrap.dedent(
                    """
                    SELECT
                      blocked_locks.pid AS blocked_pid,
                      blocked_locks.locktype as blocked_locktype,
                      blocked_locks.mode as blocked_mode,
                      blocked_activity.query AS blocked_statement,
                      blocking_locks.pid AS blocking_pid,
                      blocking_locks.locktype as blocking_locktype,
                      blocking_locks.mode as blocking_mode,
                      blocking_activity.query AS current_statement_in_blocking_process,
                      pc.relname as relname
                    FROM pg_catalog.pg_locks blocked_locks
                      JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
                      JOIN pg_catalog.pg_locks blocking_locks
                        ON blocking_locks.locktype = blocked_locks.locktype
                        AND blocking_locks.DATABASE IS NOT DISTINCT FROM blocked_locks.DATABASE
                        AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
                        AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
                        AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
                        AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
                        AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
                        AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
                        AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
                        AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
                        AND blocking_locks.pid != blocked_locks.pid
                      JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
                      LEFT JOIN pg_class as pc ON blocking_locks.relation = pc.oid
                        WHERE NOT blocked_locks.GRANTED
                    """
                )
            )
            return _results_dicts(cursor)


class DbzExplainData(DbzDataView):
    returns_list = True

    def get_ajax_data(self):
        sql = self.request.GET["sql"]
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(f"EXPLAIN {sql}")
                return cursor.fetchall()
                # plan_json = cursor.fetchone()[0][0]  # Note: Cursor already returns JSON.
                # print(json.dumps(plan_json, indent=2))
                # return plan_json
        except DBError as e:
            raise self.Error(e.__cause__)


def _results_dicts(cursor):
    """Returns a list of dicts of col name -> col value."""
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_views_urls(db_name: str):
    view_urls = [
        path("", Dbz.as_view(), name=f"dbz-{db_name}-{db_name}"),
        path("backends", DbzBackends.as_view(), name=f"dbz_backends-{db_name}"),
        path("backends/data", DbzBackendsData.as_view(), name=f"dbz_backends_data-{db_name}"),
        path("locks", DbzLocks.as_view(), name=f"dbz_locks-{db_name}"),
        path("locks/data", DbzLocksData.as_view(), name=f"dbz_locks_data-{db_name}"),
        path("blocked_locks", DbzBlockedLocks.as_view(), name=f"dbz_blocked_locks-{db_name}"),
        path("blocked_locks/data", DbzBlockedLocksData.as_view(), name=f"dbz_blocked_locks_data-{db_name}"),
        path("explain", DbzExplain.as_view(), name=f"dbz_explain-{db_name}"),
        path("explain/data", DbzExplainData.as_view(), name=f"dbz_explain_data-{db_name}"),
        path("bgwriter", DbzBgWriter.as_view(), name=f"dbz_bgwriter-{db_name}"),
    ]
    return view_urls
