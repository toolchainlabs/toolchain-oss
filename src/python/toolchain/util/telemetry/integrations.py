# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from opentelemetry.instrumentation.botocore import BotocoreInstrumentor  # type: ignore[attr-defined]
from opentelemetry.instrumentation.django import DjangoInstrumentor  # type: ignore[attr-defined]
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor  # type: ignore[attr-defined]
from opentelemetry.instrumentation.jinja2 import Jinja2Instrumentor  # type: ignore[attr-defined]
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor  # type: ignore[attr-defined]


def start_integrations() -> None:
    # https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/botocore/botocore.html
    BotocoreInstrumentor().instrument()

    # https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/django/django.html
    DjangoInstrumentor().instrument()

    # https://github.com/open-telemetry/opentelemetry-python-contrib/tree/main/instrumentation/opentelemetry-instrumentation-httpx
    HTTPXClientInstrumentor().instrument()

    # https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/psycopg2/psycopg2.html
    Psycopg2Instrumentor().instrument()

    # https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/jinja2/jinja2.html
    Jinja2Instrumentor().instrument()
