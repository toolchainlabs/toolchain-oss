# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from contextlib import contextmanager

import sentry_sdk
from sentry_sdk import configure_scope
from sentry_sdk.integrations.django import DjangoIntegration

from toolchain.constants import ToolchainServiceInfo

_logger = logging.getLogger(__name__)


class SentryEventsFilter:
    def __init__(self, *exceptions: type[Exception]):
        self._exceptions_types = set(exceptions)
        self._cookie_names = {"toolshed", "refreshToken"}

    def _scrub_request(self, request):
        if "cookies" in request:
            cookies = request["cookies"]
            for cookie_name in self._cookie_names:
                cookies.pop(cookie_name, None)

    def before_send(self, event, hint):
        if "request" in event:
            self._scrub_request(event["request"])
        if "exc_info" not in hint:
            return event
        exc_type, exc_value, tb = hint["exc_info"]
        if type(exc_value) in self._exceptions_types:
            return None
        return event


def init_sentry_for_django(
    *, dsn: str, environment: str, service_info: ToolchainServiceInfo, events_filter: SentryEventsFilter
):
    if not dsn:
        _logger.warning("No sentry DSN. Sentry is disabled.")
        return None
    # Maybe we should not do this in dev... not sure. We can decide once we have prod.
    release = service_info.commit_sha
    _logger.info(
        f"Init sentry for Django. release={release or 'NA'} environment={environment} service_name={service_info.name} service_type={service_info.service_type}"
    )
    # https://docs.sentry.io/error-reporting/configuration/?platform=python
    integration = DjangoIntegration(transaction_style="function_name")
    client = sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        send_default_pii=True,
        release=release,
        before_send=events_filter.before_send,
        integrations=[integration],
    )
    set_context(service_type=service_info.service_type, service_name=service_info.name)
    return client


def set_context(**kwargs):
    with configure_scope() as scope:
        for key, value in kwargs.items():
            scope.set_tag(key, value)


def capture_exception(exception: BaseException):
    sentry_sdk.capture_exception(error=exception)


@contextmanager
def execution_scope_context(*, prefix: str, tags: dict[str, str], extra: dict[str, str]):
    with configure_scope() as scope:
        for key, value in tags.items():
            scope.set_tag(f"{prefix}{key}", value)
        for key, value in extra.items():
            scope.set_extra(f"{prefix}{key}", value)
        yield
