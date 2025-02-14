# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config


def get_loggers_config(log_level: int, handler: str) -> dict:
    return {
        "": {"handlers": [handler], "level": log_level},
        "toolchain": {"level": log_level},
        # for httpx see: https://www.python-httpx.org/logging/
        "httpx": {"level": "WARNING"},
        "httpcore": {"level": "WARNING"},
    }


def configure_for_tool(log_level: int) -> None:
    loggers = get_loggers_config(log_level, handler="console")
    filters = {"source_path_filter": {"()": "toolchain.util.logging.filters.SourcePathLoggingFilter"}}
    formatters = {
        "default": {
            "datefmt": "%Y-%m-%d %H:%M:%S",
            "format": "[%(asctime)s %(levelname)s %(pathname)s:%(lineno)s] %(message)s",
        }
    }
    handlers = {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "default",
            "filters": ["source_path_filter"],
        }
    }
    logging.config.dictConfig(
        {
            "disable_existing_loggers": False,
            "root": {"handlers": ["console"], "level": log_level},
            "loggers": loggers,  # type: ignore[typeddict-item]
            "version": 1,
            "formatters": formatters,
            "filters": filters,
            "handlers": handlers,
        }
    )
