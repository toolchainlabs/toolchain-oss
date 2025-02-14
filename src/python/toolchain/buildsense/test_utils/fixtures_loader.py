# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
from typing import Any

import pkg_resources


def load_fixture(fixture_name: str) -> dict[str, Any]:
    return json.loads(load_bytes_fixture(f"{fixture_name}.json"))


def load_xml_fixture(fixture_name: str) -> str:
    return load_bytes_fixture(f"{fixture_name}.xml").decode()


def load_bytes_fixture(fixture_name: str) -> bytes:
    return pkg_resources.resource_string(__name__, f"fixtures/{fixture_name}")
