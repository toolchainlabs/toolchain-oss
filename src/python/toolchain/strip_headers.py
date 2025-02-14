# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).
import argparse
import re
import string
import subprocess
from pathlib import Path
from typing import Iterator

HEADERS = [
    # Python/Shell/Terraform/etc.
    (
        re.compile(
            r"""(?P<shebang>(#[^\n]*\n)*)\s*# Copyright . (?P<year>[^\n]*) Toolchain Labs, Inc\. All rights reserved\.
#
# Toolchain Labs, Inc\. CONFIDENTIAL
#
# This file includes unpublished proprietary source code of Toolchain Labs, Inc\.
# The copyright notice above does not evidence any actual or intended publication of such source code\.
# Disclosure of this source code or any related proprietary information is strictly prohibited without
# the express written permission of Toolchain Labs, Inc\.[^\n]*\s*"""
        ),
        string.Template(
            """# Copyright $year Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE)."""
        ),
    ),
    # Rust/Java/Go/etc.
    (
        re.compile(
            r"""\s*// Copyright . (?P<year>[^\n]*) Toolchain Labs, Inc\. All rights reserved\.
//
// Toolchain Labs, Inc\. CONFIDENTIAL
//
// This file includes unpublished proprietary source code of Toolchain Labs, Inc\.
// The copyright notice above does not evidence any actual or intended publication of such source code\.
// Disclosure of this source code or any related proprietary information is strictly prohibited without
// the express written permission of Toolchain Labs, Inc\.[^\n]*\s*"""
        ),
        string.Template(
            """// Copyright $year Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE)."""
        ),
    ),
    # Html.
    (
        re.compile(
            r"""\s*{#\s*
\s*Copyright . (?P<year>[^\n]*) Toolchain Labs, Inc. All rights reserved\.
\s*
\s*Toolchain Labs, Inc\. CONFIDENTIAL
\s*
\s*This file includes unpublished proprietary source code of Toolchain Labs, Inc\.
\s*The copyright notice above does not evidence any actual or intended publication of such source code\.
\s*Disclosure of this source code or any related proprietary information is strictly prohibited without
\s*the express written permission of Toolchain Labs, Inc\.
\s*#}\s*"""
        ),
        string.Template(
            """{#
Copyright $year Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
#}"""
        ),
    ),
    # Html (wrapped).
    (
        re.compile(
            r"""\s*{#\s*Copyright © (?P<year>[^\n]*) Toolchain Labs, Inc. All rights reserved. Toolchain Labs,\
\s*Inc. CONFIDENTIAL This file includes unpublished proprietary source code of\
\s*Toolchain Labs, Inc. The copyright notice above does not evidence any actual or\
\s*intended publication of such source code. Disclosure of this source code or any\
\s*related proprietary information is strictly prohibited without the express\
\s*written permission of Toolchain Labs, Inc.\s*#}\s*"""
        ),
        string.Template(
            """{#
Copyright $year Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
#}"""
        ),
    ),
    # JS.
    (
        re.compile(
            r"""\s*/\*
Copyright . (?P<year>[^\n]*) Toolchain Labs, Inc. All rights reserved\.

Toolchain Labs, Inc\. CONFIDENTIAL

This file includes unpublished proprietary source code of Toolchain Labs, Inc\.
The copyright notice above does not evidence any actual or intended publication of such source code\.
Disclosure of this source code or any related proprietary information is strictly prohibited without
the express written permission of Toolchain Labs, Inc\.
\*/
\s*"""
        ),
        string.Template(
            """/*
Copyright $year Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/"""
        ),
    ),
]


def strip_headers(dry_run: bool) -> None:
    for f in get_files():
        try:
            content = Path(f).read_text()
        except ValueError:
            # Likely a binary file.
            continue

        for existing_header_re, new_header_template in HEADERS:
            matched = existing_header_re.match(content)

            if matched:
                try:
                    prefix = matched.group("shebang")
                except IndexError:
                    prefix = ""
                header = new_header_template.safe_substitute(year=matched.group("year"))
                content = prefix + header + "\n\n" + content[len(matched.group()) :]
                if dry_run:
                    print(f"Would have adjusted {f}")
                else:
                    Path(f).write_text(content)
                    print(f"Adjusted {f}")
                break


def get_files() -> Iterator[str]:
    res = subprocess.run(
        ["git", "ls-tree", "--full-tree", "--name-only", "-r", "HEAD"], check=True, capture_output=True
    )
    for line in res.stdout.splitlines():
        yield line.decode()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="")
    parser.add_argument(
        "--no-dry-run", action="store_false", dest="dry_run", default=True, help="Run without making changes."
    )

    args = parser.parse_args()
    strip_headers(args.dry_run)
