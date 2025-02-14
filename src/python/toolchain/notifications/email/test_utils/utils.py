# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json

import pkg_resources


def load_fixture(fixture_name: str):
    return json.loads(pkg_resources.resource_string(__name__, f"fixtures/{fixture_name}.json"))
