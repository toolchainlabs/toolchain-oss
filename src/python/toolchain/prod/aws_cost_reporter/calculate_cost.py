# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# This is based on https://github.com/iandees/aws-billing-to-slack however, we want to run it as a k8s job and not as a lambda function

import datetime
from dataclasses import dataclass

from toolchain.aws.cost_explorer import CostExplorer, CostSpan
from toolchain.base.datetime_tools import utcnow

sparks = ["▁", "▂", "▃", "▄", "▅", "▆", "▇"]  # Leaving out the full block because Slack doesn't like it: '█'


@dataclass
class CostReport:
    table: str
    summary: str

    def to_message(self) -> str:
        return f"{self.summary}\n\n```\n{self.table}\n```"


def sparkline(datapoints) -> str:
    lower = min(datapoints)
    upper = max(datapoints)
    width = upper - lower
    n_sparks = len(sparks) - 1

    line = ""
    for dp in datapoints:
        scaled = 1 if width == 0 else (dp - lower) / width
        which_spark = int(scaled * n_sparks)
        line += sparks[which_spark]

    return line


def get_cost_report(aws_region: str, num_of_rows: int) -> CostReport:
    n_days = 7
    today = utcnow().date()
    week_ago = today - datetime.timedelta(days=n_days)
    cost_explorer = CostExplorer(region=aws_region)
    most_expensive_yesterday = cost_explorer.get_span_cost(week_ago, today)
    return generate_cost_report(most_expensive_yesterday, n_days, num_of_rows)


def generate_cost_report(most_expensive_yesterday: CostSpan, n_days: int, num_of_rows: int) -> CostReport:
    lines = [f"{'Service':<40} {'Last 7d':<7} ${'Yday':>5}"]
    for service_name, costs in most_expensive_yesterday[:num_of_rows]:
        costs_line = sparkline(costs)
        lines.append(f"{service_name:<40} {costs_line} ${costs[-1]:5.2f}")

    other_costs = [0.0] * n_days
    for _, costs in most_expensive_yesterday[num_of_rows:]:
        for i, cost in enumerate(costs):
            other_costs[i] += cost
    other_costs_line = sparkline(other_costs)
    lines.append(f"{'Other':<40} {other_costs_line} ${other_costs[-1]:5.2f}")

    total_costs = [0.0] * n_days
    for day_number in range(n_days):
        for _, costs in most_expensive_yesterday:
            try:
                total_costs[day_number] += costs[day_number]
            except IndexError:
                total_costs[day_number] += 0.0
    total_costs_line = sparkline(total_costs)
    lines.append(f"{'Total':<40} {total_costs_line} ${total_costs[-1]:5.2f}")
    summary = f"Yesterday's cost was ${total_costs[-1]:5.2f}."
    return CostReport(table="\n".join(lines), summary=summary)
