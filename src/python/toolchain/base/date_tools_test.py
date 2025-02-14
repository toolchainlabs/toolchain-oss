# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

from toolchain.base.date_tools import get_dates_range


def test_get_date_range_dates() -> None:
    assert get_dates_range(datetime.date(2021, 2, 25), datetime.date(2021, 3, 2)) == (
        datetime.date(2021, 2, 25),
        datetime.date(2021, 2, 26),
        datetime.date(2021, 2, 27),
        datetime.date(2021, 2, 28),
        datetime.date(2021, 3, 1),
        datetime.date(2021, 3, 2),
    )


def test_get_date_range_datetime() -> None:
    assert get_dates_range(datetime.datetime(2020, 2, 26, tzinfo=datetime.timezone.utc), datetime.date(2020, 3, 2)) == (
        datetime.date(2020, 2, 26),
        datetime.date(2020, 2, 27),
        datetime.date(2020, 2, 28),
        datetime.date(2020, 2, 29),
        datetime.date(2020, 3, 1),
        datetime.date(2020, 3, 2),
    )
