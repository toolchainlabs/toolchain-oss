# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# A docker image for building pexes with native wheels that can run in our prod environment.

# Same base image as the images we deploy.
FROM python:3.9.12-slim-buster@sha256:62ed2b347a385102d33f5e82530862359f8dc60464674d78cef844b02d150a50


ARG toolchain_user_uid

# Binaries needed to bootstrap and run Pants.
# Git is needed so pants can get version information into PEX-INFO

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    curl gcc libssl-dev git unzip python3-distutils python3-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Must have go since the pants backend uses it.
# Keep in sync with prod/docker/ci/Dockerfile.pants
# Go - https://go.dev/dl/ 
ARG golang_version=1.19.5
ARG golang_sha256="36519702ae2fd573c9869461990ae550c8c0d955cd28d2827a6b159fda81ff95"

RUN curl --fail -L -o go.tar.gz "https://dl.google.com/go/go${golang_version}.linux-amd64.tar.gz" && \
  echo "${golang_sha256}  go.tar.gz" | sha256sum -c - && \
  mkdir /usr/local/go && \
  tar xzvf go.tar.gz -C /usr/local/go --strip-components=1 && \
  ln -s "/usr/local/go/bin/go" "/usr/local/bin/go" && \
  ln -s "/usr/local/go/bin/gofmt" "/usr/local/bin/gofmt" && \
  rm go.tar.gz

ENV GOROOT=/usr/local/go


# For DRY in this file, not intended to be overridden at build time.
ARG toolchain_repo=/toolchain/host_repo
ARG bootstrap_cache=/toolchain/.cache

RUN mkdir /toolchain && \
    useradd --no-log-init -u ${toolchain_user_uid} --user-group --home /toolchain toolchain && \
    chown toolchain:toolchain /toolchain && \
    mkdir ${bootstrap_cache} && \
    chown toolchain:toolchain ${bootstrap_cache}

USER toolchain

# Mount point for the host's toolchain repo, so we can build directly from the host's source files.
VOLUME ${toolchain_repo}

# Mount point for the pants bootstrap cache, so we can conserve it between container runs.
VOLUME ${bootstrap_cache}

WORKDIR ${toolchain_repo}

ENV PANTS_WORKDIR="${toolchain_repo}/.docker.pants.d" PANTS_DISTDIR="${toolchain_repo}/dist.docker"
ENV PANTS_BUILD_IGNORE="+['/${PANTS_DISTDIR}/']" PANTS_IGNORE="+['/${PANTS_DISTDIR}']"

# We run pants onece (to build PEX files), so pantsd is not required. Also, Pantsd
# doesn't work w/ Docker under Apple M1
ENV PANTS_PANTSD=false
# needed for Apple M1
ENV PANTS_WATCH_FILESYSTEM=false
ENV PANTS_DYNAMIC_UI=false

ENTRYPOINT ["./pants"]
