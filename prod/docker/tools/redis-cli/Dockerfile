# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

FROM python:3.9.12-slim-buster@sha256:62ed2b347a385102d33f5e82530862359f8dc60464674d78cef844b02d150a50

RUN apt-get update && \
    apt-get install --no-install-recommends -y redis-tools less && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["/bin/bash"]
