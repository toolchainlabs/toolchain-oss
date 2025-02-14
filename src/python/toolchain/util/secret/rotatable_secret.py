# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import base64
import json
import time
import zlib
from contextlib import contextmanager

from toolchain.base.toolchain_error import ToolchainAssertion


class RotatableSecret:
    """A secret that can be rotated.

    The raw secret string stored in the underlying secrets manager is a "statemap" - a JSON dict mapping
    staging labels to values.  Each value is represented as an "envelope" - a dict wrapping the
    opaque secret string, plus info about its state transitions, for auditing.

    The rotation process is designed to be restartable at any point, and is as follows, using the example of db creds:

    1. Atomically: Set PROPOSED new creds, and if PROPOSED creds already existed, append those to REMOVABLE.

    2. Create the creds in the db, if they don't already exist.

    3. Atomically: Promote the PROPOSED creds to CURRENT, appending the old CURRENT creds to PREVIOUS.

    4. Ensure that the CURRENT creds are used by *all* clients. E.g., roll all servers.

    5. Move the PREVIOUS creds to REMOVABLE.

    6. Ensure that all creds in REMOVABLE are deleted from the db.

    7. Move all creds in REMOVABLE to REMOVED.

    8. From time to time: Prune REMOVED, to save space.

    External locking is assumed so that only one process at a time is applying the rotation logic for a given secret,
    to avoid race conditions.
    TODO: Can we provably eliminate race conditions?

    Note that we implement our own secrets rotation and don't rely on AWS's staging labels and versions, so that
    we can use the same rotation logic on any secrets source (e.g., AWS Secrets Manager, Kubernetes Secrets, Vault).
    """

    # Staging labels
    # --------------

    # The current value of the secret.  Represented as a singleton list, for uniformity.
    CURRENT = "CURRENT"

    # A list of previous values that may still be in use.
    PREVIOUS = "PREVIOUS"

    # A proposed new value for the secret.  Represented as a singleton list, for uniformity.
    PROPOSED = "PROPOSED"

    # A list of previous values that are definitely not in use.
    REMOVABLE = "REMOVABLE"

    # A list of previous values that have been fully removed. Kept only for auditing/debugging.  Can be pruned.
    REMOVED = "REMOVED"

    # Envelope keys
    # -------------

    # The actual string value returned to the client.
    VALUE = "VALUE"

    # A list of transition records (used for auditing).
    TRANSITIONS = "TRANSITIONS"

    # Transition record keys
    # ----------------------

    # Timestamp of the transition (in seconds since the epoch).
    TIMESTAMP = "TIMESTAMP"

    # The label transitioned from (None for a newly-proposed value).
    FROM_LABEL = "FROM_LABEL"

    # The label transitioned to.
    TO_LABEL = "TO_LABEL"

    def __init__(self, secrets_accessor, secret_name, compressed=False, clock=time.time):
        """
        :param SecretsAccessor secrets_accessor: How we access the underlying secrets manager.
        :param str secret_name: The name of the secret in the underlying secrets manager.
        :param bool compressed: Whether to compress the statemap for storage in the underlying secrets manager.
                                Compressed data is base64-encoded, to ensure compatibility with secrets managers
                                that require text secrets.
        :param callable clock: A function that returns the current time in seconds since the epoch.
                               Injectable for ease of testing.
        """
        self._secrets_accessor = secrets_accessor
        self._secret_name = secret_name
        self._compressed = compressed
        self._clock = clock
        self._now = None

    def get_current_value(self) -> str | None:
        """Return the current value of this secret.

        :return: the current secret value.
        :rtype: str
        """
        statemap = self._load_statemap()
        return statemap[self.CURRENT][0][self.VALUE] if self.CURRENT in statemap else None

    def propose_value(self, value: str) -> None:
        """Set the proposed value of this secret.

        :param str value: The proposed value of this secret.
        """
        with self._statemap() as statemap:
            if self.PROPOSED in statemap:
                self._transition(statemap, self.PROPOSED, self.REMOVABLE)
            statemap[self.PROPOSED] = [
                {self.VALUE: value, self.TRANSITIONS: [self._make_transition_record(None, self.PROPOSED)]}
            ]

    @property
    def has_proposed_value(self) -> bool:
        statemap = self._load_statemap()
        return self.PROPOSED in statemap

    def get_in_use_secrets(self):
        """Returns all the secrets that are or might be still in use."""
        statemap = self._load_statemap()
        for state in [self.CURRENT, self.PREVIOUS, self.PROPOSED]:
            for secret_state in statemap.get(state, []):
                yield secret_state[self.VALUE]

    def promote_proposed_value_to_current(self) -> bool:
        """Promote the proposed value to be the new current value.

        :return: True if a proposed value was available and promoted to current. Otherwise, False.
        :rtype: bool
        """
        with self._statemap() as statemap:
            if self.PROPOSED not in statemap:
                return False
            self._transition(statemap, self.CURRENT, self.PREVIOUS)
            self._transition(statemap, self.PROPOSED, self.CURRENT)
            return True

    def make_previous_values_removable(self) -> None:
        """Move all previous values to the removable label."""
        with self._statemap() as statemap:
            self._transition(statemap, self.PREVIOUS, self.REMOVABLE)

    def remove_removable_values(self) -> None:
        """Move all removable values to the removed label."""
        with self._statemap() as statemap:
            self._transition(statemap, self.REMOVABLE, self.REMOVED)

    def prune_removed_values(self, num_to_keep: int) -> None:
        """Prune the removed values list, keeping just the most recent num_to_keep ones."""
        with self._statemap() as statemap:
            if self.REMOVED in statemap:
                statemap[self.REMOVED] = statemap[self.REMOVED][-num_to_keep:]

    def _transition(self, statemap: dict, from_label: str, to_label: str) -> None:
        if from_label not in statemap:
            return
        if to_label not in statemap:
            statemap[to_label] = []
        for envelope in statemap[from_label]:
            transitions = envelope[self.TRANSITIONS]
            transitions.append(self._make_transition_record(from_label, to_label))
            statemap[to_label].append(envelope)
        del statemap[from_label]

    @contextmanager
    def _statemap(self):
        # Use the same timestamp for all transitions within this context.
        self._now = int(self._clock())
        statemap = self._load_statemap()
        yield statemap
        self._save_statemap(statemap)
        self._now = None

    def _load_statemap(self) -> dict:
        statemap_str = self._secrets_accessor.get_secret(self._secret_name)
        if statemap_str is None:
            return {}
        else:
            if self._compressed:
                uncompressed_statemap_str = zlib.decompress(base64.b64decode(statemap_str)).decode("utf8")
            else:
                uncompressed_statemap_str = statemap_str
            return json.loads(uncompressed_statemap_str)

    def _save_statemap(self, statemap: dict) -> None:
        uncompressed_statemap_str = json.dumps(statemap)
        if self._compressed:
            statemap_str = base64.b64encode(zlib.compress(uncompressed_statemap_str.encode("utf8"))).decode()
        else:
            statemap_str = uncompressed_statemap_str
        self._secrets_accessor.set_secret(self._secret_name, statemap_str)

    def _make_transition_record(self, from_label: str | None, to_label: str) -> dict:
        if self._now is None:
            raise ToolchainAssertion("Cannot call _make_transition_record() outside a statemap context.")
        return {self.TIMESTAMP: self._now, self.FROM_LABEL: from_label, self.TO_LABEL: to_label}
