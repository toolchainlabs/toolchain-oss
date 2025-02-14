# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.config.services import ToolchainService, get_gunicorn_service


def _get_k8s_service_domain(namespace: str, service: ToolchainService) -> str:
    k8s_svc_name = service.name
    return f"{k8s_svc_name}.{namespace}.svc.cluster.local"


def get_gunicorn_service_endpoint(django_settings, service_name: str) -> str:
    service = get_gunicorn_service(service_name)
    if django_settings.IS_RUNNING_ON_K8S:
        svc_domain = _get_k8s_service_domain(django_settings.NAMESPACE, service)
        return f"http://{svc_domain}:80/"
    # local dev (e.g.: manage.py runserver)
    return f"http://localhost:{service.dev_port}/"
