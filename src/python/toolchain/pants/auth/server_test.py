# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import socket
from contextlib import contextmanager

import pytest
import requests

from toolchain.pants.auth.server import AuthFlowHttpServer


@contextmanager
def use_tcp_ports(ports):
    used_sockets = []
    for port in ports:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            server_socket.bind(("localhost", port))
        except OSError:
            continue
        used_sockets.append(server_socket)
    yield
    for server_socket in used_sockets:
        server_socket.close()


@pytest.mark.parametrize(
    ("used_ports", "expected_port"),
    [([], 8000), ([8000, 8001, 8002, 8004], 8003), ([8000, 8001, 8002, 8003, 8004, 8005, 8006], 8007)],
)
def test_server_skip_used_ports(used_ports: list[int], expected_port: int) -> None:
    with use_tcp_ports(used_ports):
        server = AuthFlowHttpServer.create_server(port=None, expected_state="festivus")
        server.socket.close()
        assert server.server_url == f"http://localhost:{expected_port}/token-callback/"


def test_server_all_ports_busy() -> None:
    with use_tcp_ports(range(8000, 8101)), pytest.raises(Exception, match="Failed to create web server"):
        AuthFlowHttpServer.create_server(port=None, expected_state="festivus")


@pytest.mark.withoutresponses()
def test_server_success() -> None:
    server = AuthFlowHttpServer.create_server(port=8000, expected_state="festivus")
    server.start_thread()
    response = requests.get(server.server_url, params={"code": "tinsel", "state": "festivus"})
    assert response.status_code == 200
    assert server.wait_for_code(timeout_sec=1) == "tinsel"
