#!/usr/bin/env python3
# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).
# ^^^^^^^^^^^^^^^^^^^^
# NOTE: This looks for a system Python and not our bootstrapped "./python" because it is used
# by the very setup scripts that bootstrap the environment in which "./python" runs.
#
# ----
# Portions Copyright © 2020 Toolchain Labs, Inc. All rights reserved.
#
# Toolchain Labs, Inc. CONFIDENTIAL
#
# This file includes unpublished proprietary source code of Toolchain Labs, Inc.
# The copyright notice above does not evidence any actual or intended publication of such source code.
# Disclosure of this source code or any related proprietary information is strictly prohibited without
# the express written permission of Toolchain Labs, Inc.
# -----
# Regex (before modification) and some code under BSD license from:
# https://github.com/python-semver/python-semver/blob/3f92aa5494252387807fefc6083c090cbc67098d/semver.py#L17
#   Copyright (c) 2013, Konstantine Rybnikov
#   All rights reserved.
#
#   Redistribution and use in source and binary forms, with or without modification,
#   are permitted provided that the following conditions are met:
#
#   Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
#   Redistributions in binary form must reproduce the above copyright notice, this
#   list of conditions and the following disclaimer in the documentation and/or
#   other materials provided with the distribution.
#
#   Neither the name of the {organization} nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
#   THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
#   ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
#   WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#   DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
#   ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#   (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
#   LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
#   ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#   (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#   SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from typing import Tuple

import re
import sys


SEMVER_REGEX = re.compile(
    r"""
        ^
        (?P<major>0|[1-9]\d*)
        (
          \.
          (?P<minor>0|[1-9]\d*)
          (
            \.
            (?P<patch>0|[1-9]\d*)
          )?
        )?
        (?:-(?P<prerelease>
            (?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)
            (?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*
        ))?
        (?:\+(?P<build>
            [0-9a-zA-Z-]+
            (?:\.[0-9a-zA-Z-]+)*
        ))?
        $
        """,
    re.VERBOSE,
)


def parse(version_str: str):
    match = SEMVER_REGEX.match(version_str)
    if match is None:
        raise ValueError("{} is not valid SemVer string".format(version_str))

    version_parts = match.groupdict()
    version_parts["major"] = int(version_parts["major"] or 0)
    version_parts["minor"] = int(version_parts["minor"] or 0)
    version_parts["patch"] = int(version_parts["patch"] or 0)

    return version_parts


def cmp_int(x: int, y: int) -> int:
    return x - y


# Compares versions numerically in order of major, minor, patch. The SemVer Spec requires ignoring `build`
# versions. It states that versions with a `prerelease` have the same precedence level, but for this use case,
# it is easier to just ignore prerelease.
def compare(left, right) -> int:
    for part in ["major", "minor", "patch"]:
        c = cmp_int(left[part], right[part])
        if c != 0:
            return c
    return 0


def split_condition(condition: str) -> Tuple[str, str]:
    i = 0
    while i < len(condition):
        if condition[i] not in ('>', '<', '='):
            break
        i += 1
    return (condition[0:i], condition[i:])


def main(args):
    left = parse(args[0])

    for condition in args[1].split(','):
        op, right_str = split_condition(condition)
        right = parse(right_str)
        c = compare(left, right)

        if op == '=':
            complies = (c == 0)
        elif op == '<':
            complies = (c < 0)
        elif op == '<=':
            complies = (c <= 0)
        elif op == '>':
            complies = (c > 0)
        elif op == '>=':
            complies = (c >= 0)
        else:
            raise ValueError("unknown operator: {}".format(op))

        if not complies:
            return 1

    # Success!
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
