# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import base64
import json
import textwrap
import zlib

import pytest

from toolchain.base.password import generate_password
from toolchain.util.secret.rotatable_secret import RotatableSecret
from toolchain.util.secret.secrets_accessor import DummySecretsAccessor


class DummyClock:
    def __init__(self):
        self._time = 0

    def tick(self):
        self._time += 1

    def __call__(self):
        return self._time


@pytest.mark.parametrize("compressed", [True, False])
def test_label_transitions(compressed):
    secret_name = "foobar"
    secrets_accessor = DummySecretsAccessor()

    def check_statemap(expected):
        s = secrets_accessor.get_secret(secret_name)
        statemap = json.loads(zlib.decompress(base64.b64decode(s)).decode("utf8") if compressed else s)
        assert expected == statemap

    clock = DummyClock()
    secret = RotatableSecret(secrets_accessor, secret_name, compressed=compressed, clock=clock)
    assert secret.get_current_value() is None

    # Propose an initial value.
    secret.propose_value("value0")
    assert secret.get_current_value() is None
    assert secret.has_proposed_value is True
    assert list(secret.get_in_use_secrets()) == ["value0"]
    check_statemap(
        {
            "PROPOSED": [
                {"VALUE": "value0", "TRANSITIONS": [{"TIMESTAMP": 0, "FROM_LABEL": None, "TO_LABEL": "PROPOSED"}]}
            ]
        }
    )

    # Propose another value (simulates the rotation crashing between proposing and promoting).
    clock.tick()
    secret.propose_value("value1")
    assert secret.get_current_value() is None
    assert secret.has_proposed_value is True
    assert list(secret.get_in_use_secrets()) == ["value1"]
    check_statemap(
        {
            "PROPOSED": [
                {"VALUE": "value1", "TRANSITIONS": [{"TIMESTAMP": 1, "FROM_LABEL": None, "TO_LABEL": "PROPOSED"}]}
            ],
            "REMOVABLE": [
                {
                    "VALUE": "value0",
                    "TRANSITIONS": [
                        {"TIMESTAMP": 0, "FROM_LABEL": None, "TO_LABEL": "PROPOSED"},
                        {"TIMESTAMP": 1, "FROM_LABEL": "PROPOSED", "TO_LABEL": "REMOVABLE"},
                    ],
                }
            ],
        }
    )

    # Promote the most recent proposal.
    clock.tick()
    result = secret.promote_proposed_value_to_current()
    assert result is True
    assert secret.has_proposed_value is False
    assert secret.get_current_value() == "value1"
    assert list(secret.get_in_use_secrets()) == ["value1"]
    check_statemap(
        {
            "CURRENT": [
                {
                    "VALUE": "value1",
                    "TRANSITIONS": [
                        {"TIMESTAMP": 1, "FROM_LABEL": None, "TO_LABEL": "PROPOSED"},
                        {"TIMESTAMP": 2, "FROM_LABEL": "PROPOSED", "TO_LABEL": "CURRENT"},
                    ],
                }
            ],
            "REMOVABLE": [
                {
                    "VALUE": "value0",
                    "TRANSITIONS": [
                        {"TIMESTAMP": 0, "FROM_LABEL": None, "TO_LABEL": "PROPOSED"},
                        {"TIMESTAMP": 1, "FROM_LABEL": "PROPOSED", "TO_LABEL": "REMOVABLE"},
                    ],
                }
            ],
        }
    )

    # try to promote when there is no prosed value
    result = secret.promote_proposed_value_to_current()
    assert result is False
    assert secret.has_proposed_value is False
    assert list(secret.get_in_use_secrets()) == ["value1"]
    check_statemap(
        {
            "CURRENT": [
                {
                    "VALUE": "value1",
                    "TRANSITIONS": [
                        {"TIMESTAMP": 1, "FROM_LABEL": None, "TO_LABEL": "PROPOSED"},
                        {"TIMESTAMP": 2, "FROM_LABEL": "PROPOSED", "TO_LABEL": "CURRENT"},
                    ],
                }
            ],
            "REMOVABLE": [
                {
                    "VALUE": "value0",
                    "TRANSITIONS": [
                        {"TIMESTAMP": 0, "FROM_LABEL": None, "TO_LABEL": "PROPOSED"},
                        {"TIMESTAMP": 1, "FROM_LABEL": "PROPOSED", "TO_LABEL": "REMOVABLE"},
                    ],
                }
            ],
        }
    )

    # Propose another value.
    clock.tick()
    secret.propose_value("value2")
    assert secret.get_current_value() == "value1"
    assert secret.has_proposed_value is True
    assert list(secret.get_in_use_secrets()) == ["value1", "value2"]
    check_statemap(
        {
            "PROPOSED": [
                {"VALUE": "value2", "TRANSITIONS": [{"TIMESTAMP": 3, "FROM_LABEL": None, "TO_LABEL": "PROPOSED"}]}
            ],
            "CURRENT": [
                {
                    "VALUE": "value1",
                    "TRANSITIONS": [
                        {"TIMESTAMP": 1, "FROM_LABEL": None, "TO_LABEL": "PROPOSED"},
                        {"TIMESTAMP": 2, "FROM_LABEL": "PROPOSED", "TO_LABEL": "CURRENT"},
                    ],
                }
            ],
            "REMOVABLE": [
                {
                    "VALUE": "value0",
                    "TRANSITIONS": [
                        {"TIMESTAMP": 0, "FROM_LABEL": None, "TO_LABEL": "PROPOSED"},
                        {"TIMESTAMP": 1, "FROM_LABEL": "PROPOSED", "TO_LABEL": "REMOVABLE"},
                    ],
                }
            ],
        }
    )

    # Promote it.
    clock.tick()
    secret.promote_proposed_value_to_current()
    assert secret.get_current_value() == "value2"
    assert secret.has_proposed_value is False
    assert list(secret.get_in_use_secrets()) == ["value2", "value1"]
    check_statemap(
        {
            "CURRENT": [
                {
                    "VALUE": "value2",
                    "TRANSITIONS": [
                        {"TIMESTAMP": 3, "FROM_LABEL": None, "TO_LABEL": "PROPOSED"},
                        {"TIMESTAMP": 4, "FROM_LABEL": "PROPOSED", "TO_LABEL": "CURRENT"},
                    ],
                }
            ],
            "PREVIOUS": [
                {
                    "VALUE": "value1",
                    "TRANSITIONS": [
                        {"TIMESTAMP": 1, "FROM_LABEL": None, "TO_LABEL": "PROPOSED"},
                        {"TIMESTAMP": 2, "FROM_LABEL": "PROPOSED", "TO_LABEL": "CURRENT"},
                        {"TIMESTAMP": 4, "FROM_LABEL": "CURRENT", "TO_LABEL": "PREVIOUS"},
                    ],
                }
            ],
            "REMOVABLE": [
                {
                    "VALUE": "value0",
                    "TRANSITIONS": [
                        {"TIMESTAMP": 0, "FROM_LABEL": None, "TO_LABEL": "PROPOSED"},
                        {"TIMESTAMP": 1, "FROM_LABEL": "PROPOSED", "TO_LABEL": "REMOVABLE"},
                    ],
                }
            ],
        }
    )

    # Make previous value removable.
    clock.tick()
    secret.make_previous_values_removable()
    assert secret.get_current_value() == "value2"
    assert list(secret.get_in_use_secrets()) == ["value2"]
    check_statemap(
        {
            "CURRENT": [
                {
                    "VALUE": "value2",
                    "TRANSITIONS": [
                        {"TIMESTAMP": 3, "FROM_LABEL": None, "TO_LABEL": "PROPOSED"},
                        {"TIMESTAMP": 4, "FROM_LABEL": "PROPOSED", "TO_LABEL": "CURRENT"},
                    ],
                }
            ],
            "REMOVABLE": [
                {
                    "VALUE": "value0",
                    "TRANSITIONS": [
                        {"TIMESTAMP": 0, "FROM_LABEL": None, "TO_LABEL": "PROPOSED"},
                        {"TIMESTAMP": 1, "FROM_LABEL": "PROPOSED", "TO_LABEL": "REMOVABLE"},
                    ],
                },
                {
                    "VALUE": "value1",
                    "TRANSITIONS": [
                        {"TIMESTAMP": 1, "FROM_LABEL": None, "TO_LABEL": "PROPOSED"},
                        {"TIMESTAMP": 2, "FROM_LABEL": "PROPOSED", "TO_LABEL": "CURRENT"},
                        {"TIMESTAMP": 4, "FROM_LABEL": "CURRENT", "TO_LABEL": "PREVIOUS"},
                        {"TIMESTAMP": 5, "FROM_LABEL": "PREVIOUS", "TO_LABEL": "REMOVABLE"},
                    ],
                },
            ],
        }
    )

    # Remove removable values.
    clock.tick()
    secret.remove_removable_values()
    assert secret.get_current_value() == "value2"
    check_statemap(
        {
            "CURRENT": [
                {
                    "VALUE": "value2",
                    "TRANSITIONS": [
                        {"TIMESTAMP": 3, "FROM_LABEL": None, "TO_LABEL": "PROPOSED"},
                        {"TIMESTAMP": 4, "FROM_LABEL": "PROPOSED", "TO_LABEL": "CURRENT"},
                    ],
                }
            ],
            "REMOVED": [
                {
                    "VALUE": "value0",
                    "TRANSITIONS": [
                        {"TIMESTAMP": 0, "FROM_LABEL": None, "TO_LABEL": "PROPOSED"},
                        {"TIMESTAMP": 1, "FROM_LABEL": "PROPOSED", "TO_LABEL": "REMOVABLE"},
                        {"TIMESTAMP": 6, "FROM_LABEL": "REMOVABLE", "TO_LABEL": "REMOVED"},
                    ],
                },
                {
                    "VALUE": "value1",
                    "TRANSITIONS": [
                        {"TIMESTAMP": 1, "FROM_LABEL": None, "TO_LABEL": "PROPOSED"},
                        {"TIMESTAMP": 2, "FROM_LABEL": "PROPOSED", "TO_LABEL": "CURRENT"},
                        {"TIMESTAMP": 4, "FROM_LABEL": "CURRENT", "TO_LABEL": "PREVIOUS"},
                        {"TIMESTAMP": 5, "FROM_LABEL": "PREVIOUS", "TO_LABEL": "REMOVABLE"},
                        {"TIMESTAMP": 6, "FROM_LABEL": "REMOVABLE", "TO_LABEL": "REMOVED"},
                    ],
                },
            ],
        }
    )

    # Prune removable values.
    clock.tick()
    secret.prune_removed_values(1)
    assert secret.get_current_value() == "value2"
    check_statemap(
        {
            "CURRENT": [
                {
                    "VALUE": "value2",
                    "TRANSITIONS": [
                        {"TIMESTAMP": 3, "FROM_LABEL": None, "TO_LABEL": "PROPOSED"},
                        {"TIMESTAMP": 4, "FROM_LABEL": "PROPOSED", "TO_LABEL": "CURRENT"},
                    ],
                }
            ],
            "REMOVED": [
                {
                    "VALUE": "value1",
                    "TRANSITIONS": [
                        {"TIMESTAMP": 1, "FROM_LABEL": None, "TO_LABEL": "PROPOSED"},
                        {"TIMESTAMP": 2, "FROM_LABEL": "PROPOSED", "TO_LABEL": "CURRENT"},
                        {"TIMESTAMP": 4, "FROM_LABEL": "CURRENT", "TO_LABEL": "PREVIOUS"},
                        {"TIMESTAMP": 5, "FROM_LABEL": "PREVIOUS", "TO_LABEL": "REMOVABLE"},
                        {"TIMESTAMP": 6, "FROM_LABEL": "REMOVABLE", "TO_LABEL": "REMOVED"},
                    ],
                }
            ],
        }
    )


def test_secret_size():
    """Sanity-check that the statemap for a real-world secret remains of reasonable size after a few rotations.

    Changes to the rotation code that increase the size of the statemap may cause this test to fail, forcing us to at
    least consider the implications of that size increase.

    For reference: AWS SecretsManager secrets must be at most 7168 bytes. Kubernetes secrets must be at most 1MB.
    """

    def rotate(secret):
        # Generate a realistic password, so it interacts realistically with compression.
        password = generate_password(32)
        newval = textwrap.dedent(
            f"""
            {{
              "engine": "postgres",
              "username": "toolchain_userdb",
              "port": "5432",
              "host": "dbname.abcdefhijklm.us-east-1.rds.amazonaws.com",
              "pgbouncers": [
                {{
                  "host": "pgbouncer.host.name",
                  "port": "6432"
                }}
              ],
              "password": "{password}",
              "dbname": "toolchain_userdb"
            }}
            """
        )
        secret.propose_value(newval)
        secret.promote_proposed_value_to_current()
        secret.make_previous_values_removable()
        secret.remove_removable_values()

    def check_size(num_rotations, compressed):
        secrets_accessor = DummySecretsAccessor()
        secret_name = "secret_name"
        secret = RotatableSecret(secrets_accessor, secret_name, compressed=compressed)
        for _ in range(num_rotations):
            rotate(secret)
        raw_secret_size = len(secrets_accessor.get_secret(secret_name))
        compression_label = "Compressed" if compressed else "Uncompressed"
        print(f"{compression_label} secret size after {num_rotations} rotations: {raw_secret_size}")
        assert raw_secret_size < 7169

    # Unsurprisingly, our statemaps are very compressible.
    check_size(num_rotations=8, compressed=False)
    check_size(num_rotations=100, compressed=True)
