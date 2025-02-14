# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import abc
import logging
import os
import sys

import django
from django.core.management import execute_from_command_line

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.config.services import ToolchainPythonService

_logger = logging.getLogger(__name__)
_service_settings_prefix = "toolchain.service."
_service_settings_suffix = ".settings"


class ToolchainDjangoService:
    """Utility class to reduce boilerplate for a Django-based service.

    - To run management commands:

      ToolchainGunicornService.from_file_name(__file__).manage()

    - To run the service in gunicorn:

      ToolchainGunicornService.from_file_name(__file__).run_gunicorn()
    """

    class InvalidServiceFile(ToolchainAssertion):
        """Indicates an invalid Django service sentinel file."""

    _SERVICE_NAME = "SERVICE_NAME"

    @classmethod
    def from_file_name(cls, file_name: str, settings_module_name: str | None = None):
        before, partition, svc_name = file_name.partition("toolchain/service/")
        last = svc_name.rfind("/")
        if not partition or not last:
            raise cls.InvalidServiceFile(f"Unexpected service package layout for {file_name}")
        if svc_name[last:] not in cls.get_entry_points():
            raise cls.InvalidServiceFile(f"Unexpected service package layout for {file_name}")
        svc_name = svc_name[:last]
        return cls(svc_name, settings_module_name=settings_module_name)

    @classmethod
    def get_entry_points(cls) -> tuple[str, ...]:
        return ("/manage.py", "/manage.pyc")

    @classmethod
    def get_service_name(cls) -> str:
        return os.environ[cls._SERVICE_NAME]

    @classmethod
    @abc.abstractmethod
    def get_service_definition(cls, service_name: str) -> ToolchainPythonService:
        """The ToolchainPythonService instance represting this service.

        Subclasses must override.
        """

    def __init__(self, service_name: str, settings_module_name: str | None = None) -> None:
        self._service = self.get_service_definition(service_name.replace("_", "-"))
        self._settings_module = self._service.module(settings_module_name or "settings")
        os.environ[self._SERVICE_NAME] = self._service.service_name

    def post_setup(self) -> None:
        """Hook for subclasses to run custom setup steps after django is ready."""

    def setup_django(self) -> None:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", self._settings_module)
        django.setup()
        self.post_setup()

    def manage(self) -> None:
        """Run manage.py for the project."""
        self.setup_django()
        self.run_manage()

    def run_manage(self) -> None:
        if "runserver" in sys.argv:
            cmd_args = list(sys.argv)
            cmd_index = cmd_args.index("runserver")
            cmd_args.insert(cmd_index + 1, str(self._service.dev_port))  # type: ignore[attr-defined]
        else:
            cmd_args = sys.argv
        execute_from_command_line(cmd_args)
