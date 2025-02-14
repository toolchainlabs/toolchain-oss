# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from dataclasses import dataclass

from toolchain.util.config.app_config import AppConfig


@dataclass(frozen=True)
class DepgraphWorkerConfig:
    bucket: str
    base_path: str
    job_container_image: str
    push_gateway_url: str | None

    @classmethod
    def from_config(cls, app_config: AppConfig) -> DepgraphWorkerConfig:
        job_config = app_config.get_config_section("JOB_CONFIG")
        return cls(
            bucket=job_config["results_bucket"],
            base_path=job_config["results_base_path"],
            job_container_image=job_config["job_image"],
            push_gateway_url=job_config.get("push_gateway_url"),
        )

    @classmethod
    def for_dev(cls, namespace: str) -> DepgraphWorkerConfig:
        return cls(
            bucket="pants-demos-dev.us-east-1.toolchain.com",
            base_path=f"{namespace}/depgraph/github/repos/",
            job_container_image="283194185447.dkr.ecr.us-east-1.amazonaws.com/pants-demos/depgraph-job:dev-latest",
            push_gateway_url=None,
        )
