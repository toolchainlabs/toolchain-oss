# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

FROM python:3.9.12-slim-buster@sha256:62ed2b347a385102d33f5e82530862359f8dc60464674d78cef844b02d150a50

ARG PEX_FILE

# https://chromedriver.storage.googleapis.com or https://chromedriver.chromium.org/downloads to dfind a list of versions
ARG CHROME_DRIVER_VERSION=90.0.4430.24
# 'apt-get update -qq && apt-cache policy chromium | grep Candidate' to latest available version
ARG CHROMIUM_VERSION=90.0.4430.212-1~deb10u1

# install chromedriver, can be improved see https://gist.github.com/mikesmullin/2636776#gistcomment-2986509
RUN apt-get update && apt-get upgrade -y && \
    apt-get install --no-install-recommends -y chromium-sandbox chromium=${CHROMIUM_VERSION} wget unzip && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    wget --quiet https://chromedriver.storage.googleapis.com/${CHROME_DRIVER_VERSION}/chromedriver_linux64.zip && \
    unzip chromedriver_linux64.zip && apt-get remove -y  unzip wget && rm chromedriver_linux64.zip && \
    mv ./chromedriver /usr/local/bin/

# The uid:gid 99:99 is nobody:nobody on our production host system (AWS's EKS-optimized AMI).
RUN groupadd --gid 99 toolchain && useradd -m --no-log-init --uid 99 --gid 99 toolchain && \
    chown toolchain:toolchain /usr/local/bin/chromedriver && chmod +x /usr/local/bin/chromedriver && \
    mkdir /pex && chown toolchain:toolchain /pex && chmod 755 /pex 

WORKDIR /pex
COPY --chown=toolchain:toolchain $PEX_FILE ./test-tool.pex

USER toolchain:toolchain
ENTRYPOINT ["/pex/test-tool.pex"]
