# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from django.db.models import Count, QuerySet

from toolchain.django.db.transaction_broker import TransactionBroker

# Utilities relating to QuerySets.


def get_rows_and_total_size(
    unlimited_qs: QuerySet, offset: int, limit: int, large_table_threshold: int = 100000
) -> tuple[list, int]:
    """Estimate the total number of rows a queryset would return if it were not range-limited.

    Useful for paginated queries - doing a precise COUNT(*) may be prohibitively expensive on large tables.

    :param unlimited_qs: The QuerySet with no [offset, offset+limit] applied.
    :param offset: The offset that was applied.
    :param limit: The limit that was applied.
    :param large_table_threshold: Use sampling for tables with more than this many rows.
    """
    # First execute the limited query.
    range_limited_rows = list(unlimited_qs[offset : offset + limit])

    # Now compute the total number of unlimited rows.
    if offset == 0 and len(range_limited_rows) < limit:
        # This spares us the extra query for the count, and also mitigates the weirdness of small results displaying
        # a count that doesn't match the number of rows the user actually sees, due to changes in state between
        # the the two queries.
        total = len(range_limited_rows)
    else:

        def exec_raw(sql, sql_params=None):
            with TransactionBroker(unlimited_qs.model._meta.app_label).connection.cursor() as cursor:
                cursor.execute(sql, sql_params)
                return cursor.fetchone()[0]

        db_table = unlimited_qs.model._meta.db_table

        # For small-ish tables, just do a count.
        total_table_size = exec_raw(
            f"SELECT reltuples::bigint FROM pg_class WHERE oid=to_regclass('public.{db_table}')"
        )
        if total_table_size < large_table_threshold:
            total = unlimited_qs.count()
        else:
            # Table is large so count queries will be expensive - use sampling instead.
            # WARNING: Raw SQL generation using Django internals. May break between Django versions.
            query = unlimited_qs.query.clone()
            query.add_annotation(Count("*"), alias="__count", is_summary=True)
            query.select = []
            query.default_cols = False
            query._extra = {}
            query.clear_ordering(True)
            query.clear_limits()
            query.select_for_update = False
            query.select_related = False
            compiler = query.get_compiler(using=unlimited_qs.db)
            raw_query, params = compiler.as_sql()
            raw_query = raw_query.replace(f'FROM "{db_table}" ', f'FROM "{db_table}" TABLESAMPLE SYSTEM (1) ')
            if " WHERE " in raw_query:
                total = exec_raw(raw_query, params)
                # Ensure that a wonky sample doesn't show something ridiculous.
                total = max(total, offset + limit + 1)
            else:
                total = total_table_size

    return range_limited_rows, total
