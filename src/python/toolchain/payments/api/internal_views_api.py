# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

from rest_framework.views import APIView, Response

from toolchain.base.datetime_tools import utcnow
from toolchain.payments.amberflo_integration.models import AmberfloCustomerMTDMetrics
from toolchain.payments.stripe_integration.models import SubscribedCustomer

_logger = logging.getLogger(__name__)


class InternalPaymentsCustomerViewView(APIView):
    def get(self, request, customer_pk: str):
        today = utcnow().date()
        month = int(request.GET.get("month", today.month))
        year = int(request.GET.get("year", today.year))
        stripe_customer = SubscribedCustomer.get_by_customer_id(customer_id=customer_pk)
        mtd_metrics = AmberfloCustomerMTDMetrics.get_metrics(customer_id=customer_pk, year=year, month=month)
        metrics = (
            {"read_bytes": mtd_metrics.cache_read_bytes, "write_bytes": mtd_metrics.cache_write_bytes}
            if mtd_metrics
            else {}
        )
        plan = (
            {
                "name": stripe_customer.plan_name,
                "price": stripe_customer.plan_price_text,
                "trial_end": stripe_customer.trial_end.isoformat() if stripe_customer.trial_end else None,
            }
            if stripe_customer
            else {}
        )
        return Response(data={"usage": metrics, "plan": plan})
