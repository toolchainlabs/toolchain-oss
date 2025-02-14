# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import argparse
import logging
import logging.config
import sys
from argparse import ArgumentParser, Namespace
from collections import OrderedDict
from typing import TypeVar

from toolchain.util.logging.config_helpers import get_loggers_config

# A forward-referencing self-type:
#  https://www.python.org/dev/peps/pep-0484/#annotating-instance-and-class-methods
T = TypeVar("T", bound="ToolchainBinary")


class ToolchainBinary:
    """Provides useful shared functionality for our Python binaries.

    Extend this in your main module, implement callbacks as needed, and add the following boilerplate to make your
    module the entry point:

    if __name__ == '__main__':   YourToolchainBinarySubclass.start()

    The binary will exit with the exit code returned by your run() method.
    """

    description: str | None = None
    DEFAULT_AWS_REGION = "us-east-1"

    _DATEFMT = "%H:%M:%S"

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        """Override this to add arguments to the provided argparse.ArgumentParser."""

    @classmethod
    def configure_logging(cls, log_level: int, use_colors: bool = True) -> None:
        """Override this to configure logging."""
        handler: dict[str, str | bool] = {
            "class": "rich.logging.RichHandler" if use_colors else "logging.StreamHandler",
            "formatter": "simple",
        }
        if use_colors:
            handler["rich_tracebacks"] = True
        logging_config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "simple": {
                    "format": "%(message)s" if use_colors else "%(asctime).19s %(levelname)-7s %(message)s",
                    "datefmt": cls._DATEFMT,
                }
            },
            "handlers": {"console": handler},
            "loggers": get_loggers_config(log_level, "console"),
        }
        logging.config.dictConfig(logging_config)

    def __init__(self, cmdline_args: Namespace) -> None:
        """Override this to perform custom initialization.

        Your binary can access the cmdline args via the cmdline_args property. It is also free to initialize its own
        state in __init__, from the cmdline_args param, and not use the self.cmdline_args property at all.  However your
        __init__ method must still call this one via super().__init__(cmdline_args), to ensure initialization.
        """
        self._cmdline_args = cmdline_args
        self._enable_colors = not cmdline_args.no_colors

    @property
    def cmdline_args(self) -> Namespace:
        return self._cmdline_args

    @property
    def enable_colors(self) -> bool:
        return self._enable_colors

    def run(self) -> int:
        """Override this to execute your program logic."""
        raise NotImplementedError()

    @classmethod
    def handle_exception(cls, error, instance) -> bool:
        """Allows subclasses to handle errors that occur durion setup or execution.

        Should return True/False based on whether the exception was handled or not.
        """
        return False

    @classmethod
    def start(cls) -> None:
        instance = None
        exit_code = -1
        try:
            args = cls._get_args()
            log_level = _name_to_log_level[args.log_level.upper()]
            cls.configure_logging(log_level, use_colors=not args.no_colors)
            instance = cls(args)
            exit_code = instance.run()
        except Exception as error:
            handled = cls.handle_exception(error=error, instance=instance)
            if not handled:
                raise
        sys.exit(exit_code)

    @classmethod
    def create_for_args(cls: type[T], **kwargs) -> T:
        """Return an instance initialized with the specified values and default for all other args.

        Useful in tests.
        """
        namespace = argparse.Namespace(**kwargs)
        parser = argparse.ArgumentParser()
        cls._add_common_arguments(parser)
        cls.add_arguments(parser)
        # The parse on an empty args list will fail if any arguments are required.
        for action in parser._actions:
            action.required = False
        for group in parser._mutually_exclusive_groups:
            group.required = False
        parser.parse_args(args=[], namespace=namespace)
        return cls(namespace)

    @classmethod
    def _get_args(cls) -> Namespace:
        description = cls.description or cls.__doc__ or f"Command line args for {cls.__name__}."
        parser = argparse.ArgumentParser(description=description)
        cls._add_common_arguments(parser)
        cls.add_arguments(parser)
        return parser.parse_args()

    @classmethod
    def add_aws_region_argument(cls, parser: ArgumentParser) -> None:
        parser.add_argument("--aws-region", default=cls.DEFAULT_AWS_REGION, help="The AWS region.", required=False)

    @classmethod
    def _add_common_arguments(cls, parser: ArgumentParser) -> None:
        log_level_choices = list(_name_to_log_level.keys())
        parser.add_argument("--log-level", choices=log_level_choices, default="INFO", help="Logging level.")
        parser.add_argument("--no-colors", action="store_true", help="Do not colorize console output.")


_log_levels = (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL)


_name_to_log_level = OrderedDict((logging.getLevelName(level), level) for level in _log_levels)
