# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.test import Client


def test_metricsz():
    response = Client().get("/metricsz")
    assert response.status_code == 200
    metrics = response.content.decode()
    assert len(metrics.split()) > 100
    assert "django_http_requests_body_total_bytes_bucket" in metrics
    assert "python_gc_objects_collected_total" in metrics
    assert "django_http_requests_latency_including_middlewares_seconds_created" in metrics
    assert "django_model_deletes_total" in metrics
