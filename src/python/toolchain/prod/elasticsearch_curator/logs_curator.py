#!/usr/bin/env ./python
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
from argparse import ArgumentParser, Namespace

import curator

from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.constants import ToolchainEnv
from toolchain.prod.elasticsearch_curator.metrics import Metrics
from toolchain.util.config.app_config import AppConfig
from toolchain.util.config.kubernetes_env import KubernetesEnv
from toolchain.util.elasticsearch.client_helper import get_open_search_client
from toolchain.util.elasticsearch.config import ElasticSearchConfig
from toolchain.util.logging.config_helpers import configure_for_tool

_logger = logging.getLogger(__name__)


class LogsCurator(ToolchainBinary):
    """Delete old logs indices from ES Domain."""

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._dry_run = cmd_args.dry_run
        self._days = cmd_args.days
        config = AppConfig.from_env()
        k8s_env = KubernetesEnv.from_config(config)
        tc_env = ToolchainEnv(config.get("TOOLCHAIN_ENV", ToolchainEnv.DEV))  # type: ignore
        aws_region = config.get("AWS_REGION")
        push_gateway_url = config.get("PUSH_GATEWAY_URL")
        es_config = ElasticSearchConfig.for_env(
            toolchain_env=tc_env, is_k8s=k8s_env.is_running_in_kubernetes, config=config
        )
        _logger.info(
            f"Config: dry_run={self._dry_run} retention_days={self._days} env={tc_env} aws_region={aws_region} push_gateway={push_gateway_url or 'NA'} {es_config}"
        )
        self._opensearch_client = get_open_search_client(es_config=es_config, aws_region=aws_region)
        self._metrics = Metrics(push_gateway_url=push_gateway_url, dry_run=self._dry_run, k8s_env=k8s_env)

    def run(self) -> int:
        self._opensearch_client.ping()
        _logger.info("ping success. looking for old indexes.")
        with self._metrics.track() as metrics:
            indices_removed = self.delete_old_logs(days=self._days, dry_run=self._dry_run)
            metrics.measure_indices_removed(indices_removed)
        return 0

    def delete_old_logs(self, days: int, dry_run: bool) -> int:
        # TODO: Add pushgateway and report number of indices we removed via prometheus metrics
        index_list = self._filter_indices(days)
        names = index_list.indices
        if not names:
            _logger.info("No indices to delete.")
            return 0
        delete_indices = curator.DeleteIndices(index_list)
        _logger.info(f"Delete {len(names)} indices dry run: {dry_run}. {','.join(names)}")
        if not dry_run:
            delete_indices.do_action()
        return len(names)

    def _filter_indices(self, days: int):
        index_list = curator.IndexList(self._opensearch_client)
        # Might want to do: index_list.filter_by_regex(kind='prefix', value='dev-logs')
        # But looks like we don't need it right now.
        index_list.filter_by_age(unit_count=days, unit="days", source="name", direction="older", timestring="%Y.%m.%d")
        return index_list

    @classmethod
    def configure_logging(cls, log_level, use_colors=True):
        configure_for_tool(log_level)

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        parser.add_argument("--dry-run", action="store_true", required=False, default=False, help="Dry run.")
        parser.add_argument(
            "--days",
            type=int,
            metavar="int",
            required=False,
            default=14,
            help="Number of days we keeps logs for (older logs will be deleted)",
        )


if __name__ == "__main__":
    LogsCurator.start()
