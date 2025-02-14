#!/usr/bin/env ./python
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import re
from pathlib import Path

import httpx
from ruamel.yaml import YAML

_CLUSTER_DS = {
    "current": {"selected": True, "text": "remoting", "value": "remoting"},
    "hide": 0,
    "includeAll": False,
    "label": "datasource",
    "multi": False,
    "name": "DS_PROMETHEUS",
    "options": [],
    "query": "prometheus",
    "queryValue": "",
    "refresh": 1,
    "regex": "/remoting/",
    "skipUrlSync": False,
    "type": "datasource",
}
# Based on https://github.com/helm/charts/blob/bb503e51e0cd312a92bf480ff9ec0d48e6cc9879/stable/prometheus-operator/hack/sync_grafana_dashboards.py

K8S_SOURCE_CHART_URL = "https://raw.githubusercontent.com/prometheus-operator/kube-prometheus/master/manifests/grafana-dashboardDefinitions.yaml"

K8S_EXCLUDES = {"etcd", "controller-manager", "scheduler"}
SCRIPT_TAG_EXPRESSION = r"\<script .*\<\/script\>"


def sync_k8s_dashboards(destination: Path, client: httpx.Client) -> None:
    response = client.get(K8S_SOURCE_CHART_URL)
    response.raise_for_status()
    groups = next(YAML().load_all(response.text))["items"]
    for group in groups:
        for resource, content in group["data"].items():
            resource_name = resource.replace(".json", "")
            if resource_name in K8S_EXCLUDES:
                continue
            (destination / resource).write_text(content)


def _update_datsources_fields(items: list[dict]):
    for item in items:
        if item.get("datasource") != "prometheus":
            continue
        item["datasource"] = "${DS_PROMETHEUS}"


def _add_datasource(dashboard: dict) -> None:
    dashboard["annotations"]["list"][0]["datasource"] = "${DS_PROMETHEUS}"
    templates = dashboard["templating"]["list"]
    _update_datsources_fields(templates)
    _update_datsources_fields(dashboard["panels"])
    templates.insert(0, _CLUSTER_DS)


def _remove_script(dashboard: dict):
    for panel in dashboard["panels"]:
        if "content" in panel and panel.get("mode") == "html":
            panel["content"] = re.sub(SCRIPT_TAG_EXPRESSION, "", panel["content"], flags=re.DOTALL).strip()


def fetch_dashboards(destination: Path) -> None:
    destination.mkdir(exist_ok=True)
    with httpx.Client() as client:
        sync_k8s_dashboards(destination, client)


if __name__ == "__main__":
    fetch_dashboards(Path("prod/helm/observability/monitoring/grafana/dashboards"))
