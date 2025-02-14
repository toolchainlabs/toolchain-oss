# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import os
import re
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from logging import LogRecord
from tempfile import TemporaryDirectory

import pkg_resources
import pytest


@contextmanager
def extract_testbin_file(pkg: str, name: str) -> Iterator[str]:
    """Yields a filesystem path, in a tmpdir, to a .testbin file embedded in package resources.

    The resulting file's name will be the .testbin file's name, with that suffix stripped.
    """
    assert name.endswith(".testbin")  # nosec: B101
    testbin_path = pkg_resources.resource_filename(pkg, name)
    with TemporaryDirectory() as tmpdir:
        tmpfile_path = os.path.join(tmpdir, os.path.splitext(os.path.basename(testbin_path))[0])
        shutil.copy(testbin_path, tmpfile_path)
        yield tmpfile_path


def assert_messages(caplog, match: str) -> LogRecord | None:
    for record in caplog.records:
        if re.search(match, record.message):
            return record
    pytest.fail(f"No log messages matching: {match}")
    return None


def to_wsgi_header(name: str) -> str:
    normalized = name.upper().replace("-", "_")
    return f"HTTP_{normalized}"


def convert_headers_to_wsgi(headers: dict[str, str]) -> dict[str, str]:
    return {to_wsgi_header(key): value for key, value in headers.items()}
