# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

ARG rust_server_base_image
# hadolint ignore=DL3006
FROM ${rust_server_base_image}

ARG rust_version

### Setup Rust development environment.
###
### Note: Vendored from https://github.com/rust-lang/docker-rust/blob/master/1.55.0/buster/slim/Dockerfile
### because there is a potential for library versions in the official Rust image and the Debian base image that we
### use for production images to be out of sync. To prevent that issue, we vendor the setup rules here and
### ensure the Rust builder and production images use the exact same base image.

ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH \
    RUST_VERSION=${rust_version}

# hadolint ignore=DL3047
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        gcc \
        g++  \
        make \
        cmake \
        ca-certificates \
        libc6-dev \
        curl \
        unzip \
        ; \
    dpkgArch="$(dpkg --print-architecture)"; \
    case "${dpkgArch##*-}" in \
        amd64) rustArch='x86_64-unknown-linux-gnu'; rustupSha256='3dc5ef50861ee18657f9db2eeb7392f9c2a6c95c90ab41e45ab4ca71476b4338' ;; \
        armhf) rustArch='armv7-unknown-linux-gnueabihf'; rustupSha256='67777ac3bc17277102f2ed73fd5f14c51f4ca5963adadf7f174adf4ebc38747b' ;; \
        arm64) rustArch='aarch64-unknown-linux-gnu'; rustupSha256='32a1532f7cef072a667bac53f1a5542c99666c4071af0c9549795bbdb2069ec1' ;; \
        i386) rustArch='i686-unknown-linux-gnu'; rustupSha256='e50d1deb99048bc5782a0200aa33e4eea70747d49dffdc9d06812fd22a372515' ;; \
        *) echo >&2 "unsupported architecture: ${dpkgArch}"; exit 1 ;; \
    esac; \
    url="https://static.rust-lang.org/rustup/archive/1.24.3/${rustArch}/rustup-init"; \
    curl --fail -LO "$url" ; \
    echo "${rustupSha256} *rustup-init" | sha256sum -c -; \
    chmod +x rustup-init; \
    ./rustup-init -y --no-modify-path --profile minimal --default-toolchain $RUST_VERSION --default-host ${rustArch}; \
    rm rustup-init; \
    chmod -R a+w $RUSTUP_HOME $CARGO_HOME; \
    rustup --version; \
    cargo --version; \
    rustc --version; \
    rm -rf /var/lib/apt/lists/*;

### End vendored steps.

ARG toolchain_repo=/toolchain/host_repo
ARG rust_version

RUN rustup component add clippy rustfmt --toolchain ${rust_version}-x86_64-unknown-linux-gnu

RUN curl --fail -o /tmp/protoc.zip -L https://github.com/protocolbuffers/protobuf/releases/download/v21.4/protoc-21.4-linux-x86_64.zip && \
    echo "d51e8f030162f08823a4738ab0ac00bee537e30b583a562e6962dbb040d86736  /tmp/protoc.zip" | sha256sum -c - && \
    mkdir -p /tmp/protoc-unpacked && \
    unzip /tmp/protoc.zip -d /tmp/protoc-unpacked && \
    cp /tmp/protoc-unpacked/bin/protoc /usr/local/bin/protoc && \
    chmod +x /usr/local/bin/protoc && \
    rm -rf /tmp/protoc-unpacked/ /tmp/protoc.zip

WORKDIR $toolchain_repo/src/rust
COPY rust_build.sh /tmp/rust_build.sh
RUN chmod 777 /tmp/rust_build.sh
ENTRYPOINT ["/tmp/rust_build.sh"]
