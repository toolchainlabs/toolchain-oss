# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import http
import time
from contextlib import suppress
from enum import Enum, unique
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer  # type: ignore
from importlib import resources
from threading import Thread
from typing import cast
from urllib.parse import parse_qsl, urlparse

from toolchain.pants.common.errors import ToolchainPluginError


@unique
class TestPage(Enum):
    NA = "na"
    SUCCESS = "success"
    ERROR = "error"


class AuthServerHandler(BaseHTTPRequestHandler):
    CALLBACK_PATH = "/token-callback/"
    TEST_SUCCESS_PATH = "/test/success/"
    TEST_ERROR_PATH = "/test/error/"

    @property
    def auth_server(self) -> AuthFlowHttpServer:
        # this property is to silence mypy/make it happy.
        return cast(AuthFlowHttpServer, self.server)

    def _serve_favicon(self) -> None:
        self.send_response(http.HTTPStatus.OK)
        self.send_header("Content-type", "image/png")
        self.end_headers()
        self.wfile.write(self.auth_server.fav_icon)

    def _accept_code(self, parsed_url) -> None:
        query = dict(parse_qsl(parsed_url.query))
        auth_error = query.get("error")
        if auth_error:
            self._serve_error_page(auth_error)
            return
        code = query["code"]
        state = query["state"]
        success, error_message = self.auth_server.set_access_token_code(code, state)
        if not success:
            self._serve_error_page(error_message)
            return
        self._serve_success_page()

    def _serve_error_page(self, error_message, http_error_status: int = http.HTTPStatus.BAD_REQUEST) -> None:
        self.send_response(http_error_status)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(self.auth_server.get_error_html(error_message))

    def _serve_success_page(self) -> None:
        self.send_response(http.HTTPStatus.OK)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(self.auth_server.success_html)

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        if parsed_url.path == "/favicon.ico":
            self._serve_favicon()
        elif parsed_url.path == self.CALLBACK_PATH:
            self._accept_code(parsed_url)
        elif parsed_url.path == self.TEST_SUCCESS_PATH:
            self._serve_success_page()
        elif parsed_url.path == self.TEST_ERROR_PATH:
            self._serve_error_page("No soup for you! come back one year!")
        else:
            self._serve_error_page(f"Invalid path: {parsed_url.path}", http_error_status=http.HTTPStatus.NOT_FOUND)


class AuthFlowHttpServer(ThreadingHTTPServer):
    @classmethod
    def create_server(cls, *, port: int | None, expected_state: str):
        if port:
            return cls(port, expected_state)
        for curr_port in range(8000, 8100):
            with suppress(OSError):
                return cls(curr_port, expected_state)
        raise ToolchainPluginError("Failed to create web server")

    def __init__(self, port, expected_state):
        super().__init__(("localhost", port), AuthServerHandler)
        self._resources = {
            "favicon": _load_resource("favicon.png"),
            "success": _load_resource("success.html"),
            "error": _load_resource("error.html").decode(),
        }
        self._thread = Thread(target=self._server_thread, daemon=True)
        self._base_server_url = f"http://localhost:{port}"
        self._callback_url = f"{self._base_server_url}{AuthServerHandler.CALLBACK_PATH}"
        self._code = None
        self._expected_state = expected_state

    def _server_thread(self):
        self.serve_forever(poll_interval=0.2)

    def start_thread(self):
        self._thread.start()

    @property
    def server_url(self) -> str:
        return self._callback_url

    def get_test_url(self, test_page: TestPage) -> str:
        path = (
            AuthServerHandler.TEST_SUCCESS_PATH if test_page == TestPage.SUCCESS else AuthServerHandler.TEST_ERROR_PATH
        )
        return f"{self._base_server_url}{path}"

    @property
    def fav_icon(self) -> bytes:
        return self._resources["favicon"]

    @property
    def success_html(self) -> bytes:
        return self._resources["success"]

    def get_error_html(self, message) -> bytes:
        error_html = self._resources["error"]
        error_html = error_html.replace("$MESSAGE", message)
        return error_html.encode()

    def set_access_token_code(self, code: str, state: str) -> tuple[bool, str]:
        if not code:
            return False, "Missing token exchange code"
        if self._expected_state != state:
            return False, f"Unexpected state value: {state} (expected {self._expected_state})"
        self._code = code
        return True, ""

    def wait_for_code(self, timeout_sec: int = 300) -> str | None:
        # TODO: Failure scenarios
        timeout_time = time.time() + timeout_sec
        while not self._code and time.time() < timeout_time:
            time.sleep(0.1)
        self.shutdown()
        return self._code


def _load_resource(name: str) -> bytes:
    # Ugly hack to get local module name. can't figure out a pythonic way to do this.
    module_name = ".".join(__name__.split(".")[:-1])
    return resources.read_binary(module_name, name)
