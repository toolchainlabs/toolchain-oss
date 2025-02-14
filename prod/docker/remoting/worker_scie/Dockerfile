# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

FROM "ubuntu:jammy-20220801@sha256:42ba2dfce475de1113d55602d40af18415897167d47c2045ec7b6d9746ff148f"
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y \
        build-essential \
        git \
        cmake \
        pkg-config \
        curl \
        libssl-dev \
        libfuse3-dev \
        uuid-dev \
        libprotobuf-dev \
        protobuf-compiler \
        libgrpc-dev \
        libgrpc++-dev \
        protobuf-compiler-grpc \
        libgtest-dev \
        libgmock-dev \
        python3 \
        python3-pip \
        bubblewrap \
        grpc++

RUN mkdir -p /build && mkdir -p /build/buildbox

COPY download_install.sh /tmp/download_install.sh
COPY download_install_tc_fork.sh /tmp/download_install_tc_fork.sh
RUN chmod +x /tmp/download_install.sh /tmp/download_install_tc_fork.sh

# https://gitlab.com/BuildGrid/buildbox/buildbox-common/-/releases/0.0.61
RUN /tmp/download_install.sh buildbox-common c5a2ee2b448c636507489fd7b26a29394e3b0edb
ENV BUILDBOX_COMMON_SOURCE_ROOT=/tmp/buildbox-common
# Use `/tmp/download_install_tc_fork.sh` instead of `/tmp/download_install_tc_fork.sh` if you need to build a component from the TC fork(s)

# https://gitlab.com/BuildGrid/buildbox/buildbox-casd/-/tags/0.0.61
RUN /tmp/download_install.sh buildbox-casd a383c732d76ebfae3cc1632b55e9134dff65dc84 YES
# https://gitlab.com/BuildGrid/buildbox/buildbox-worker/-/tags/0.0.61
RUN /tmp/download_install.sh buildbox-worker 9565a93292b04e103d62817153553d62c6f9237e YES
#  No tags. https://gitlab.com/BuildGrid/buildbox/buildbox-run-hosttools/-/tags
RUN /tmp/download_install.sh buildbox-run-hosttools 5fc4184de288f19d40a90c6498462f57de49539d YES
RUN mv /build/usr/local/bin/buildbox-casd /build/buildbox/buildbox-casd && \
    mv /build/usr/local/bin/buildbox-worker /build/buildbox/buildbox-worker && \
    mv /build/usr/local/bin/buildbox-run-hosttools /build/buildbox/buildbox-run-hosttools

# https://github.com/a-scie/jump/releases/tag/v0.10.0
ARG scie_jump_version=0.10.0
ARG scie_jump_sha256="6dc9c7edd1f088b3a2718ee5740a9f9243516e5cd087557546f35af2e0a5fa8c" # For linux_x86_64

RUN curl --fail -L https://github.com/a-scie/jump/releases/download/v${scie_jump_version}/scie-jump-linux-x86_64 -o /build/scie-jump && \
   echo "${scie_jump_sha256} /build/scie-jump" | sha256sum -c && \
   chmod +x /build/scie-jump

COPY worker /build/worker
COPY lift.json /build/lift.json

WORKDIR /build
RUN ./scie-jump
