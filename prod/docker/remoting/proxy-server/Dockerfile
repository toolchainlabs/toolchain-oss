# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

ARG rust_server_base_image
FROM ${rust_server_base_image}

RUN apt-get update && apt-get install --no-install-recommends -y gdb && apt-get clean

ADD ./proxy_server /usr/local/bin/proxy_server
RUN chown root:root /usr/local/bin/proxy_server && chmod 755 /usr/local/bin/proxy_server

# Create toolchain user that the utility will run as. (User created as a disabled user hence the /bin/false shell.)
RUN mkdir -p /toolchain && \
  groupadd --gid 99 toolchain && useradd -m --no-log-init --uid 99 --gid 99 toolchain && \
  chown toolchain:toolchain /toolchain && chmod 755 /toolchain

USER toolchain:toolchain
WORKDIR /toolchain
ENTRYPOINT ["/usr/local/bin/proxy_server"]
