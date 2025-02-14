# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
from argparse import ArgumentParser, Namespace
from time import sleep

from toolchain.base.env_args import StoreWithEnvDefault
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.util.config.app_config import AppConfig
from toolchain.util.config.kubernetes_env import KubernetesEnv
from toolchain.util.file.argument_types import directory_url, local_directory_url
from toolchain.util.leveldb.syncer import Syncer
from toolchain.util.logging.config_helpers import configure_for_tool

logger = logging.getLogger(__name__)


class WatcherTool(ToolchainBinary):
    """Polls for new leveldbs under a (typically remote) dir and fetches the latest one to a local dir.

    Typically used in concert with ReloadableDataset. See there for details.
    """

    def __init__(self, cmdline_args: Namespace) -> None:
        super().__init__(cmdline_args)
        self._period_secs = cmdline_args.period_secs
        if len(cmdline_args.remote_basedir_urls) != len(cmdline_args.local_basedir_urls):
            raise ToolchainAssertion("Number of remote URLs and local directories doesn't match.")
        pairs = zip(cmdline_args.remote_basedir_urls, cmdline_args.local_basedir_urls)
        config = AppConfig.from_env()
        k8s_namespace = KubernetesEnv.from_config(config).namespace
        push_gateway_url = config.get("PUSH_GATEWAY_URL")
        logger.info(
            f"Init WatcherTool period_secs={self._period_secs} pairs={pairs} k8s_namespace={k8s_namespace} push_gateway={push_gateway_url or 'NA'}"
        )
        self._syncers = [
            Syncer(remote_basedir_url=remote_base, local_basedir_url=local_base) for remote_base, local_base in pairs
        ]

    def run(self) -> int:
        while True:
            self.check_latest()
            logger.info(f"Sleeping for {self._period_secs} seconds.")
            sleep(self._period_secs)
            self.cleanup()

    def check_latest(self) -> None:
        for syncer in self._syncers:
            syncer.check_latest()

    def cleanup(self) -> None:
        for syncer in self._syncers:
            # We assume that we can clean up old data, as enough time has passed for consumers to
            # pick up the new one. If this turns out to be an issue, we can add proper synchronization.
            syncer.cleanup()

    @classmethod
    def configure_logging(cls, log_level, use_colors=True) -> None:
        configure_for_tool(log_level)

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        def get_semicolon_delimited_type(underlying_type):
            def _semicolon_delimited_values(vals):
                return [underlying_type(val) for val in vals.split(";")]

            return _semicolon_delimited_values

        parser.add_argument(
            "--remote-basedir-urls",
            type=get_semicolon_delimited_type(directory_url),
            required=True,
            action=StoreWithEnvDefault,
            help="URLs of remote base dir containing leveldbs (delimited w/ semicolons).",
        )
        parser.add_argument(
            "--local-basedir-urls",
            type=get_semicolon_delimited_type(local_directory_url),
            required=True,
            action=StoreWithEnvDefault,
            help="URLs of local base dir to fetch leveldbs to (delimited w/ semicolons).",
        )
        parser.add_argument(
            "--period-secs",
            type=int,
            default=5 * 60,
            action=StoreWithEnvDefault,
            help="Check for new leveldbs every this many seconds.",
        )


if __name__ == "__main__":
    WatcherTool.start()
