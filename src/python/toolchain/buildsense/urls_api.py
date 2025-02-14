# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.urls import include, path
from rest_framework import routers

from toolchain.buildsense import views_api as buildsense_api
from toolchain.buildsense.ingestion import views_api as ingestion_api

builds_router = routers.SimpleRouter()
builds_router.register("builds", buildsense_api.BuildViewSet, basename="builds")


view_urls = builds_router.urls + [
    path("builds/<run_id>/artifacts/<artifact_id>/", buildsense_api.BuildArtifactsView.as_view(), name="artifacts"),
]

ingest_url = [
    path("buildsense/batch/", ingestion_api.BuildsenseBatchIngestionView.as_view(), name="buildsense-batch"),
    path("buildsense/<run_id>/", ingestion_api.BuildsenseIngestionView.as_view(), name="buildsense-ingest"),
    path("buildsense/", ingestion_api.BuildsenseConfig.as_view(), name="buildsense-config"),
    path(
        "buildsense/<run_id>/workunits/",
        ingestion_api.WorkunitsIngestionView.as_view(),
        name="buildsense-workunits-ingest",
    ),
    path(
        "buildsense/<run_id>/artifacts/",
        ingestion_api.ArtifactsIngestionView.as_view(),
        name="buildsense-artifacts-ingest",
    ),
]


app_name = "buildsense_api"


urlpatterns = [
    path("api/v1/repos/<customer_slug>/<repo_slug>/", include(view_urls + ingest_url)),
]
