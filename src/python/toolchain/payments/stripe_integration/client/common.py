# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from urllib.parse import urljoin

import httpx

from toolchain.config.endpoints import get_gunicorn_service_endpoint
from toolchain.django.site.middleware.request_context import get_current_request_id
from toolchain.util.constants import REQUEST_ID_HEADER
from toolchain.util.net.httpx_util import get_timeout_retry_client


def get_http_client(django_settings, url_prefix: str = "", timeout: int = 3) -> httpx.Client:
    base_url = get_gunicorn_service_endpoint(django_settings, "payments/api")
    service_name = django_settings.SERVICE_INFO.name
    base_url = urljoin(base_url, url_prefix) if url_prefix else base_url
    headers = {"User-Agent": f"Toolchain-Internal/{service_name}"}
    req_id = get_current_request_id()
    if req_id:
        headers[REQUEST_ID_HEADER] = req_id
    return get_timeout_retry_client(
        service_name=service_name,
        timeout_retries=4,
        base_url=base_url,
        headers=headers,
        timeout=timeout,
        transport=httpx.HTTPTransport(retries=4),
    )
