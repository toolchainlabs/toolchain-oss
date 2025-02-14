# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# We use the non-slim version since it is needed when pyenv tries to install different python versions.
FROM python:3.9.12-buster@sha256:b323ae34296b212cb4a219fa03e7e87d3d177839a4d50ab7970a05a05e3a82a2

RUN apt-get update && \
    apt-get install --no-install-recommends -y \ 
        curl git unzip gcc libssl-dev bash build-essential && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    groupadd --gid 99 toolchain && useradd -m --no-log-init --uid 99 --gid 99 toolchain

ARG golang_version=1.19.5
ARG golang_sha256="36519702ae2fd573c9869461990ae550c8c0d955cd28d2827a6b159fda81ff95"

RUN curl --fail -L -o go.tar.gz "https://dl.google.com/go/go${golang_version}.linux-amd64.tar.gz" && \
  echo "${golang_sha256}  go.tar.gz" | sha256sum -c - && \
  mkdir "/usr/local/go${golang_version}" && \
  tar xzvf go.tar.gz -C "/usr/local/go${golang_version}" --strip-components=1 && \
  rm go.tar.gz && \
  ln -s "/usr/local/go${golang_version}/bin/go" "/usr/local/bin/go" && \
  ln -s "/usr/local/go${golang_version}/bin/gofmt" "/usr/local/bin/gofmt"

ENV GOROOT="/usr/local/go${golang_version}"

# https://github.com/pyenv/pyenv/releases/tag/v2.3.15
ARG pyenv_commit_sha="6bb75b3ba79a7f9b6c2eae7fe2d7521e315cc04a"
# https://github.com/pyenv/pyenv#basic-github-checkout
RUN git clone --filter=tree:0 https://github.com/pyenv/pyenv /usr/local/pyenv/
WORKDIR /usr/local/pyenv/
RUN git checkout ${pyenv_commit_sha} && rm -rf .git && \
    bash -C src/configure && make -C src

USER toolchain:toolchain

COPY --chown=toolchain:toolchain pants-bootstrap.sh /home/toolchain/
WORKDIR /home/toolchain
ENV PATH=$PATH:/usr/local/pyenv/bin
ARG PY_VERSION=3.11.2
RUN pyenv install ${PY_VERSION}
# The version here must match the version in src/python/toolchain/pants_demos/depgraph/job/resources/pants.toml
ARG PANTS_VERSION=2.15.0

RUN ./pants-bootstrap.sh "${PANTS_VERSION}" && rm pants-bootstrap.sh
COPY --chown=toolchain:toolchain pants-demo.pex /home/toolchain/

ENTRYPOINT ["./pants-demo.pex", "--git-mode", "http"]