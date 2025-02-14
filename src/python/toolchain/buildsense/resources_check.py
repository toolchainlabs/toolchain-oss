# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.conf import settings
from django.http import JsonResponse
from django.views import View

from toolchain.buildsense.ingestion.metrics_store import PantsMetricsStore
from toolchain.buildsense.ingestion.models import check_ingestion_models_access
from toolchain.buildsense.ingestion.run_info_raw_store import RunInfoRawStore
from toolchain.buildsense.ingestion.run_info_table import RunInfoTable
from toolchain.buildsense.search.run_info_search_index import RunInfoSearchIndex
from toolchain.django.site.models import Repo, check_models_read_access


class DependentResourcesCheckz(View):
    view_type = "checks"

    def get(self, _):
        users_db = check_models_read_access()
        buildsense_db = check_ingestion_models_access()
        repo = Repo.get_random()
        search = RunInfoSearchIndex.for_customer_id(settings=settings, customer_id=repo.customer_id)
        table = RunInfoTable.for_customer_id(customer_id=repo.customer_id)
        opensearch_check = search.check_access()
        s3_check = RunInfoRawStore.check_access(repo)
        dynamodb_check = table.check_access(repo)
        influxdb = PantsMetricsStore.check_access()
        access_results = {
            "users_db": users_db,
            "buildsense_db": buildsense_db,
            "opensearch": opensearch_check,
            "s3": s3_check,
            "dynamodb": dynamodb_check,
            "influxdb": influxdb,
        }
        return JsonResponse(data=access_results)
