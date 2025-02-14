# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import base64
import json
import logging

from toolchain.django.site.middleware.request_context import get_current_request


class RequestLoggingFilter(logging.Filter):
    """Adds data from the request to the logging record and makes them available to logging formatters."""

    def filter(self, record):
        request_id = ""
        session_id = ""
        user = None
        request = get_current_request()
        if request:
            request_id = getattr(request, "request_id", "")
            # We want to avoid the side effect fo loading the user (in cases where it is not already loaded)
            # The django auth middleware will attach a SimpleLazyObject to request.user, so calling
            # request.user.pk from this code will trigger a side effect of loading the user from the DB.
            # logging shouldn't have side effect.
            # We should figure out a better solution, such as moving away from the Django auth middleware
            user = getattr(request, "_cached_user", None)
            session_id = request.session.session_key if hasattr(request, "session") else ""
        record.request_id = request_id
        record.session_id = session_id
        record.user_info = f"{user.username}/{user.api_id}" if user and user.is_authenticated else ""
        return super().filter(record)


def from_base64_json(base64_str):
    if not base64_str:
        return None
    return json.loads(base64.b64decode(base64_str))


def get_logging_config(config=None, service_type=None):
    log_level = (config.get("LOG_LEVEL", "") if config else "").upper() or "INFO"
    if service_type == "api":
        log_fmt = (
            "[%(asctime)s %(levelname)s %(process)d %(pathname)s:%(lineno)s request_id=%(request_id)s] %(message)s"
        )
    elif service_type in {"web-ui", "web-ui-marketing"}:
        log_fmt = (
            "[%(asctime)s %(levelname)s %(process)d %(pathname)s:%(lineno)s request_id=%(request_id)s] %(message)s"
        )
    elif service_type == "admin":
        log_fmt = "[%(asctime)s %(levelname)s %(process)d %(pathname)s:%(lineno)s %(user_info)s session_id=%(session_id)s request_id=%(request_id)s] %(message)s"
    elif service_type and "worker" in service_type:
        log_fmt = "[%(asctime)s %(levelname)s %(threadName)s %(pathname)s:%(lineno)s] %(message)s"
    else:
        log_fmt = "[%(asctime)s %(levelname)s %(process)d %(pathname)s:%(lineno)s] %(message)s"
    loggers = {
        "": {
            "handlers": ["console"],
            # Don't switch this to DEBUG, because it will emit debug logging from all python modules,
            # which can cause secrets retrieved from secretsmanager to be logged by the underlying networking code.
            # If you need to control the log level of specific modules, list them below.
            "level": "INFO",
        },
        "django": {"level": "INFO"},
        # Set to 'DEBUG' to log all SQL queries.
        "django.db": {"level": log_level},
        "toolchain": {"level": log_level},
        # for httpx see: https://www.python-httpx.org/logging/
        "httpx": {"level": "WARNING"},
        "httpcore": {"level": "WARNING"},
    }

    logging_config = {
        "loggers": loggers,
        "version": 1,
        "disable_existing_loggers": False,  # So we don't stomp on gunicorn's logging config.
        "formatters": {"default": {"format": log_fmt, "datefmt": "%Y-%m-%d %H:%M:%S"}},
        "filters": {
            "source_path_filter": {"()": "toolchain.util.logging.filters.SourcePathLoggingFilter"},
            "request_filter": {"()": "toolchain.django.site.logging.logging_helpers.RequestLoggingFilter"},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "DEBUG",
                "formatter": "default",
                "filters": ["request_filter", "source_path_filter"],
            }
        },
    }
    return logging_config
