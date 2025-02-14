# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json

import pkg_resources


def load_fixture(fixture_name: str) -> dict:
    return json.loads(pkg_resources.resource_string(__name__, f"fixtures/{fixture_name}.json"))


def load_fixture_payload(fixture_name: str) -> dict:
    fixture = load_fixture(fixture_name)
    return fixture["payload"]
