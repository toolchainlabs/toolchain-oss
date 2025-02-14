# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

from dateutil.rrule import DAILY, rrule


def get_dates_range(
    from_date: datetime.date | datetime.datetime, to_date: datetime.date | datetime.datetime
) -> tuple[datetime.date, ...]:
    dtstart = from_date.date() if isinstance(from_date, datetime.datetime) else from_date
    until = to_date.date() if isinstance(to_date, datetime.datetime) else to_date
    return tuple(dt.date() for dt in rrule(DAILY, dtstart=dtstart, until=until))
