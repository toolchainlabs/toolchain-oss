# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

FROM python:3.9.12-slim-buster@sha256:62ed2b347a385102d33f5e82530862359f8dc60464674d78cef844b02d150a50

RUN apt-get update && \
    apt-get install --no-install-recommends -y git unzip gcc libssl-dev bash && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    groupadd --gid 99 toolchain && useradd -m --no-log-init --uid 99 --gid 99 toolchain

USER toolchain:toolchain

RUN mkdir /home/toolchain/projects
WORKDIR /home/toolchain/projects

RUN git clone https://bitbucket.org/festivus-miracle/minimal-pants.git
WORKDIR /home/toolchain/projects/minimal-pants
RUN git checkout 7d5036be9d811240d792d5210805de6af10e0b81
COPY pants.e2e-tests.toml pants.e2e-tests.toml
RUN ./pants --version
COPY run_pants.sh /tmp/run_pants.sh
ENTRYPOINT ["/tmp/run_pants.sh"]
