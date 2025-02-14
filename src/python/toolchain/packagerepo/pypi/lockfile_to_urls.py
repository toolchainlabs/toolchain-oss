# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from toolchain.base.toolchain_error import ToolchainError
from toolchain.packagerepo.pypi.lockfile_parser import parse_lockfile
from toolchain.packagerepo.pypi.models import Distribution


def lockfile_to_urls(lockfile_path: str):
    urls = []
    for project_name, version, sha256 in parse_lockfile(lockfile_path):
        url = Distribution.get_url_for_locked_version(project_name, version, sha256)
        if url is None:
            raise ToolchainError(f"Found no URL for {project_name}:{version}#{sha256}")
        urls.append(url)
    return urls


def lockfile_to_urls_output(lockfile_path: str, output_path: str | None = None) -> None:
    urls = lockfile_to_urls(lockfile_path)
    if output_path:
        with open(output_path, "w", encoding="utf-8") as fp:
            for url in urls:
                fp.write(url)
                fp.write("\n")
    else:
        for url in urls:
            print(url)
