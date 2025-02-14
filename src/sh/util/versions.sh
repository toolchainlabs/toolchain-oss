#!/usr/bin/env bash
# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

function current_tag() {
  # We prefix the git hash with the commit's timestamp, so that the tags sort chronologically.
  # This makes it easier to clean up old images from the ECR repository.
  #
  # For example:
  # git show: 2018-09-11T23:43:14+00:00@2262b5e3464d007ca27b8972a9448a15de5a4539
  # final:    2018-09-11.23-43-14-2262b5e3464d
  #
  TZ=UTC git show -s --format=%cd@%H --date=iso-strict-local HEAD |
    sed -E -f <(
      cat << EOF
# Drop the UTC timezone
s|\+00:00||

# <date>.<time> instead of <date>T<time>
s|T|.|

# H-M-S instead of H:M:S
s|:|-|g

# Just the leading 12 characters of the full commit sha.
s|@(.{12}).*$|-\1|
EOF
    )
}
