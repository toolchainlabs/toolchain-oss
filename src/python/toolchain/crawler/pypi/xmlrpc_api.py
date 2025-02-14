# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# We use the PyPI XMLRPC API, even though it is intended to be deprecated at some point in the future:
# https://warehouse.readthedocs.io/api-reference/xml-rpc/.  Currently there are no alternatives for the
# mirroring-related endpoints we need.
# We could use bandersnatch, which is the official PyPI mirror client. However it's not designed for our
# use case, so we would have to rely on its internals, and it's not clear which parts of those are stable
# and which can change without notice. Plus, it uses the XMLRPC API for its internal implementation anyway.

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from xmlrpc.client import ProtocolError, SafeTransport, ServerProxy

from toolchain.crawler.pypi.exceptions import TransientError
from toolchain.lang.python.distributions.distribution_key import canonical_project_name

_logger = logging.getLogger(__name__)


AllProjects = dict[str, int]


@dataclass(frozen=True)
class ChangeLogEntry:
    project: str
    version: str
    filename: str
    serial: int


@dataclass(frozen=True)
class ChangeLog:
    added: tuple[ChangeLogEntry, ...]
    removed: tuple[ChangeLogEntry, ...]

    @classmethod
    def from_lists(cls, *, added: list[ChangeLogEntry], removed: list[ChangeLogEntry]) -> ChangeLog:
        return cls(added=tuple(added), removed=tuple(removed))

    def __str__(self) -> str:
        return f"change_log added={len(self.added)} removed={len(self.removed)}"


class ToolchainTransport(SafeTransport):
    user_agent = "ops-mgmt@toolchain.com"


class RateLimitedServerProxy(ServerProxy):
    # See https://github.com/pypa/warehouse/issues/8753#issuecomment-718475928
    def __init__(self) -> None:
        super().__init__(uri="https://pypi.org/pypi", transport=ToolchainTransport())

    def __getattr__(self, name: str):
        time.sleep(1)
        try:
            return super().__getattr__(name)
        finally:
            time.sleep(1)


class ApiClient:
    def __init__(self):
        self._client = RateLimitedServerProxy()

    def get_last_serial(self) -> int:
        try:
            return self._client.changelog_last_serial()
        except ProtocolError as error:
            _logger.warning(f"Protocol error calling changelog_last_serial {error!r}", exc_info=True)
            raise TransientError(f"Protocol error calling changelog_last_serial {error!r}")

    def get_all_projects(self) -> AllProjects:
        """Returns a map of project name to latest serial for that project."""
        return {
            canonical_project_name(name): serial for name, serial in self._client.list_packages_with_serial().items()
        }

    def get_changed_packages(self, serial_from: int, serial_to: int) -> ChangeLog:
        """Gets all packages that have changed from serial_from (inclusive) to serial_to (exclusive)."""
        added_files: list[ChangeLogEntry] = []
        removed_files: list[ChangeLogEntry] = []
        # The changelog_since_serial API is not inclusive, i.e. if you ask for changes since X, change w/ serial X is not included.
        # So we ask for X-1 so that change will be included.
        try:
            change_log_entries = self._client.changelog_since_serial(serial_from - 1)
        except ProtocolError as error:
            _logger.warning(f"Protocol error calling changelog_since_serial {error!r}", exc_info=True)
            raise TransientError(f"Protocol error calling changelog_since_serial {error!r}")
        for project, version, _, action, serial in change_log_entries:
            if serial >= serial_to:
                continue
            project = canonical_project_name(project)
            action_parts = action.split(" ")
            if action_parts[0] == "add" and action_parts[2] == "file":
                # E.g., `add source file foo-0.1.0.tar.gz`, `add py2.py3 file foo-0.1.0-py2.py3-none-any.whl`.
                added_files.append(
                    ChangeLogEntry(project=project, version=version, filename=action_parts[3], serial=serial)
                )
            elif action_parts[0] == "remove" and action_parts[1] == "file":
                # E.g., `remove file foo-0.1.0.tar.gz`, `remove file foo-0.1.0-py2.py3-none-any.whl`.
                removed_files.append(
                    ChangeLogEntry(project=project, version=version, filename=action_parts[2], serial=serial)
                )
        return ChangeLog.from_lists(added=added_files, removed=removed_files)
