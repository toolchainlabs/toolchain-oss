# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
from collections import defaultdict

from toolchain.aws.aws_api import AWSService

CostSpan = list[tuple[str, list[float]]]


class CostExplorer(AWSService):
    service = "ce"
    _COST_QUERY = {
        "Granularity": "DAILY",
        "Filter": {"Not": {"Dimensions": {"Key": "RECORD_TYPE", "Values": ["Credit", "Refund", "Upfront", "Support"]}}},
        "Metrics": ["UnblendedCost"],
        "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}],
    }

    def get_span_cost(self, from_date: datetime.date, to_date: datetime.date) -> CostSpan:
        period = {"Start": from_date.strftime("%Y-%m-%d"), "End": to_date.strftime("%Y-%m-%d")}
        result = self.client.get_cost_and_usage(TimePeriod=period, **self._COST_QUERY)
        cost_per_day_by_service: dict[str, list[float]] = defaultdict(list)
        # Build a map of service -> array of daily costs for the time frame
        for day in result["ResultsByTime"]:
            for group in day["Groups"]:
                key = group["Keys"][0]
                cost = float(group["Metrics"]["UnblendedCost"]["Amount"])
                cost_per_day_by_service[key].append(cost)
        # Sort the map by to_date-1d (usually yesterday) cost
        return sorted(cost_per_day_by_service.items(), key=lambda i: i[1][-1], reverse=True)
