# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest
from django.db.models import F

from toolchain.django.db.qs_util import get_rows_and_total_size
from toolchain.django.db.testapp.models import Number


@pytest.mark.django_db()
def test_get_rows_and_total_size_unfiltered():
    # Test on an unfiltere query.
    def get_total(expected_rows):
        qs = Number.objects.all()
        rows, tot = get_rows_and_total_size(unlimited_qs=qs, offset=0, limit=20, large_table_threshold=50)
        assert list(range(0, expected_rows)) == [num.value for num in rows]
        return tot

    for i in range(0, 10):
        Number.objects.create(value=i)

    # Exact count for result smaller than limit.
    assert get_total(10) == 10

    for i in range(10, 30):
        Number.objects.create(value=i)

    # Exact count for table smaller than large_table_threshold.
    assert get_total(20) == 30

    for i in range(30, 100):
        Number.objects.create(value=i)

    # Approximate count for table larger than large_table_threshold.
    assert 0 <= get_total(20) <= 110


@pytest.mark.django_db()
def test_get_rows_and_total_size_filtered():
    # Test on a query with a filter.
    def get_total(expected_rows):
        qs = Number.objects.annotate(odd=F("value") % 2).filter(odd=False)
        rows, tot = get_rows_and_total_size(unlimited_qs=qs, offset=0, limit=10, large_table_threshold=50)
        assert list(range(0, expected_rows * 2, 2)) == [num.value for num in rows]
        return tot

    for i in range(0, 10):
        Number.objects.create(value=i)

    # Exact count for result smaller than limit.
    assert get_total(5) == 5

    for i in range(10, 30):
        Number.objects.create(value=i)

    # Exact count for table smaller than large_table_threshold.
    assert get_total(10) == 15

    for i in range(30, 100):
        Number.objects.create(value=i)

    # Approximate count for table larger than large_table_threshold.
    assert 0 <= get_total(10) <= 55
