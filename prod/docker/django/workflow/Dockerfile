# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# We'd prefer to use alpine, but manylinux wheels don't work on it, and building the
# native wheels from scratch doesn't seem worth it.
FROM python:3.9.12-slim-buster@sha256:62ed2b347a385102d33f5e82530862359f8dc60464674d78cef844b02d150a50

ARG MANAGE_PY_MODULE
ARG PEX_FILE
ARG COMMIT_SHA

# Thes utils are useful to have when debugging in the container.  We immediately clean up the
# apt cache and package metadata, so it doesn't bloat the image.
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends curl tmux procps && \
    apt-get -y clean && rm -rf /var/lib/apt/lists/* && \
    # The uid:gid 99:99 is nobody:nobody on our production host system (AWS's EKS-optimized AMI).
    groupadd --gid 99 toolchain && useradd -m --no-log-init --uid 99 --gid 99 toolchain && \
    mkdir /pex && chown toolchain:toolchain /pex && chmod 755 /pex 

COPY  greeting.sh /etc/profile.d/greeting.sh
RUN chmod +x /etc/profile.d/greeting.sh && echo ". /etc/profile.d/greeting.sh" >> /etc/bash.bashrc

USER toolchain:toolchain

WORKDIR /pex

COPY --chown=toolchain:toolchain ${PEX_FILE} ./workflow-server.pex

# Create a wrapper script to invoke manage.py directly out of the pex.
# We use the script in this Dockerfile, but it's also useful when exec'ing into a running container.
RUN echo "PEX_MODULE=${MANAGE_PY_MODULE} ./workflow-server.pex \"\$@\"" >> ./manage.py && chmod 755 ./manage.py

ENV GIT_COMMIT_SHA=${COMMIT_SHA}

CMD ["/pex/workflow-server.pex"]
