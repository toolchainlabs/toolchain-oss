# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

FROM python:3.9.12-slim-buster@sha256:62ed2b347a385102d33f5e82530862359f8dc60464674d78cef844b02d150a50

ARG PEX_FILE
RUN apt-get update && apt-get upgrade -y && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    # The uid:gid 99:99 is nobody:nobody on our production host system (AWS's EKS-optimized AMI).
    groupadd --gid 99 toolchain && useradd -m --no-log-init --uid 99 --gid 99 toolchain && \
    mkdir /pex && chown toolchain:toolchain /pex && chmod 755 /pex 

USER toolchain:toolchain

WORKDIR /pex

COPY --chown=toolchain:toolchain $PEX_FILE ./tool.pex
ENTRYPOINT ["/pex/tool.pex"]
