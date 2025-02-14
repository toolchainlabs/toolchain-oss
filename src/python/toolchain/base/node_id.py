# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import os
import socket


def get_node_id() -> str:
    """Returns an identifier of the node this binary is running on.

    Useful for logging, status reporting etc.

    The exact meaning of "node" depends on implementation details of deployment environments, but useful examples
    include Kubernetes pod name, host:port, host.pid etc. (Do not confuse with a Kubernetes node, which is an entire
    host).
    """
    return os.environ.get("K8S_POD_NAME") or f"{socket.gethostname()}.{os.getpid()}"
