# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
import threading
from typing import Callable

from django.conf import settings
from django.core.servers.basehttp import WSGIRequestHandler, WSGIServer, get_internal_wsgi_application

from toolchain.config.services import ToolchainPythonService, get_workflow_service
from toolchain.django.aws.config import configure_aws_for_django
from toolchain.django.service.toolchain_django_service import ToolchainDjangoService
from toolchain.workflow.maintenance_web_app_init import run_workflow_maintenance_forever

_logger = logging.getLogger(__name__)


class ToolchainWSGIRequestHandler(WSGIRequestHandler):
    suppress_logs = True

    def log_message(self, format, *args):
        if self.suppress_logs and args and "GET /metricsz" in args[0]:
            return
        super().log_message(format, *args)


class DjangoWsgiServer:
    def __init__(self, local_addr: str, port: int) -> None:
        self._local_addr = local_addr
        self._server = None
        self._port = port

    def run_server_in_thread(self) -> None:
        self._wsgi_thread = threading.Thread(target=self.run_server, daemon=True, name="wsgi_server")
        self._wsgi_thread.start()

    def _create_server(self) -> WSGIServer:
        server_address = (self._local_addr, self._port)
        wsgi_handler = get_internal_wsgi_application()
        _logger.info(f"DjangoWsgiServer Create - {server_address=}")
        httpd = WSGIServer(server_address, ToolchainWSGIRequestHandler, ipv6=False)
        httpd.set_app(wsgi_handler)
        return httpd

    def run_server(self) -> None:
        self._server = self._create_server()
        _logger.info("DjangoWsgiServer Serve")
        try:
            self._server.serve_forever()  # type: ignore[attr-defined]
        finally:
            _logger.info("DjangoWsgiServer exit")


class ToolchainWorkflowService(ToolchainDjangoService):
    @classmethod
    def get_service_definition(cls, service_name: str) -> ToolchainPythonService:
        return get_workflow_service(service_name)

    @classmethod
    def get_entry_points(cls) -> tuple[str, ...]:
        return super().get_entry_points() + (
            "/workflow_worker_main.py",
            "/workflow_worker_main.pyc",
            "/workflow_maintenance_main.py",
            "/workflow_maintenance_main.pyc",
        )

    def _start_wsgi_server(self, alternative_port: bool) -> None:
        if settings.IS_RUNNING_ON_K8S:
            local_addr = "0.0.0.0"
            port = 8001
        else:
            local_addr = "127.0.0.1"
            port = 8002 if alternative_port else 8001
        self._wsgi_server = DjangoWsgiServer(local_addr=local_addr, port=port)
        self._wsgi_server.run_server_in_thread()

    def run_workflow_server(self, workflow_dispatcher_callback: Callable, suppress_logs: bool = True) -> None:
        self.setup_django()
        configure_aws_for_django()
        ToolchainWSGIRequestHandler.suppress_logs = suppress_logs
        # TODO: run checks cmd.check(display_num_errors=True) and cmd.check_migrations()
        workflow_dispatcher_cls = workflow_dispatcher_callback()
        self._start_wsgi_server(alternative_port=False)
        workflow_dispatcher_cls.for_django(settings.WORKFLOW_WORKER_CONFIG).run_workflow_forever()

    def manage(self) -> None:
        self.setup_django()
        configure_aws_for_django()
        self.run_manage()

    def run_workflow_maintenance(self) -> None:
        self.setup_django()
        self._start_wsgi_server(alternative_port=True)
        run_workflow_maintenance_forever(settings)
