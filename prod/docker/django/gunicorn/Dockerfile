# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# We'd prefer to use alpine, but manylinux wheels don't work on it, and building the
# native wheels from scratch doesn't seem worth it.
FROM python:3.9.12-slim-buster@sha256:62ed2b347a385102d33f5e82530862359f8dc60464674d78cef844b02d150a50

ARG MANAGE_PY_MODULE
ARG PEX_FILE
ARG COLLECT_STATIC=1
ARG COMMIT_SHA

# Thes utils are useful to have when debugging in the container.  We immediately clean up the
# apt cache and package metadata, so it doesn't bloat the image.
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends curl tmux procps && \
    apt-get -y clean && rm -rf /var/lib/apt/lists/* && \
# The uid:gid 99:99 is nobody:nobody on our production host system (AWS's EKS-optimized AMI).
    groupadd --gid 99 toolchain && useradd -m --no-log-init --uid 99 --gid 99 toolchain && \
    mkdir -p /var/log/gunicorn/ && chown toolchain:toolchain /var/log/gunicorn/ && chmod 755 /var/log/gunicorn/ && \
    mkdir -p /var/run/gunicorn/ && chown toolchain:toolchain /var/run/gunicorn/ && chmod 755 /var/run/gunicorn/ && \
    mkdir /pex && chown toolchain:toolchain /pex && chmod 755 /pex && \
    mkdir /staticfiles && chown toolchain:toolchain /staticfiles && chmod 755 /staticfiles

COPY  greeting.sh /etc/profile.d/greeting.sh
RUN chmod +x /etc/profile.d/greeting.sh && echo ". /etc/profile.d/greeting.sh" >> /etc/bash.bashrc

USER toolchain:toolchain

WORKDIR /pex

COPY --chown=toolchain:toolchain ${PEX_FILE} ./gunicorn.pex

# Create a wrapper script to invoke manage.py directly out of the pex.
# We use the script in this Dockerfile, but it's also useful when exec'ing into a running container.
RUN echo "PEX_MODULE=${MANAGE_PY_MODULE} ./gunicorn.pex \"\$@\"" >> ./manage.py && chmod 755 ./manage.py

# Collect the static files into /staticfiles.  This dir is shared with the fronting nginx via a docker volume.
# Note: We may not have permissions to access secrets at build time, nor do we need them (or databases)
# in order to run collectstatic, so we run this in a TOOLCHAIN_ENV that doesn't attempt to set those up.
# NB we don't use `ENV` because we don't want the TOOLCHAIN_ENV value to exist at container runtime.
RUN test "${COLLECT_STATIC}" = 1 || exit 0 && TOOLCHAIN_ENV=toolchain_collectstatic ./manage.py collectstatic --noinput

ENV GIT_COMMIT_SHA=${COMMIT_SHA}

CMD ["/pex/gunicorn.pex"]
