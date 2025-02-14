# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import importlib.util
import logging

from gunicorn.app.wsgiapp import WSGIApplication

from toolchain.config.services import ToolchainPythonService, get_gunicorn_service
from toolchain.django.aws.config import configure_aws_for_django
from toolchain.django.service.toolchain_django_service import ToolchainDjangoService

_logger = logging.getLogger(__name__)


class ToolchainWSGIApplication(WSGIApplication):
    """Configures the gunicorn wsgi app.

    Simplifies configuring it: Avoids putting stuff in sys.args just for logic in BaseApplication.load_config to parse
    it out Allows hooking logic to run after loading the app (in load_wsgiapp)
    """

    _WSGI_APP_MODULE = "toolchain.django.service.gunicorn.wsgi"

    @classmethod
    def run_app(cls, conf_module: str) -> None:
        gunicorn_conf_path = f"python:{conf_module}"
        cls(gunicorn_conf_path).run()

    def __init__(self, gunicorn_conf_path: str):
        self._gc_conf_path = gunicorn_conf_path
        # Base class's __init__ will end up calling load_config(), so self._gc_conf_path is initialized before calling super().
        super().__init__()

    def load_config(self) -> None:
        self._custom_load_cfg()

    def _custom_load_cfg(self) -> None:
        self.cfg.set("default_proc_name", self._WSGI_APP_MODULE)
        self.app_uri = self._WSGI_APP_MODULE
        conf_path = self._gc_conf_path
        self.load_config_from_file(conf_path)
        self.cfg.set("config", conf_path)
        _logger.info(f"Loaded config from: {conf_path}")

    def load_wsgiapp(self):
        app = super().load_wsgiapp()
        # We can run some post-load logic here
        return app


class ToolchainGunicornService(ToolchainDjangoService):
    @classmethod
    def get_service_definition(cls, service_name: str) -> ToolchainPythonService:
        return get_gunicorn_service(service_name)

    @classmethod
    def get_entry_points(cls) -> tuple[str, ...]:
        return super().get_entry_points() + ("/gunicorn_main.py", "/gunicorn_main.pyc")

    def _get_conf_module(self) -> str:
        # See if the settings module has a sibling module named gunicorn_conf.
        conf_module = self._service.module("gunicorn_conf")
        # See if the service-specific gunicorn_conf.py exists, without importing it.
        if importlib.util.find_spec(conf_module) is None:
            # Fall back to the default gunicorn_conf.py.
            conf_module = "toolchain.django.service.gunicorn.gunicorn_conf"
        return conf_module

    def run_gunicorn(self) -> None:
        """Run gunicorn for the project."""
        self.setup_django()
        ToolchainWSGIApplication.run_app(self._get_conf_module())

    def post_setup(self) -> None:
        # TODO: we don't need to call this for infosite, and we don't want infosite to import this.
        configure_aws_for_django()
