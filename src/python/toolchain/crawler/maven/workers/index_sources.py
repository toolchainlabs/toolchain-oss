# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import os
import re
import subprocess
import sys
import textwrap
from tempfile import TemporaryDirectory

from toolchain.base.fileutil import safe_mkdir
from toolchain.base.toolchain_error import ToolchainAssertion, ToolchainError
from toolchain.packagerepo.maven.coordinates import GAVCoordinates

BUILD_TEMPLATE = textwrap.dedent(
    """
    remote_sources(
      name='lib',
      dest=java_library,
      sources_target=':lib-unpacked-jar',
      dependencies=[
        ':lib-binary-jar',
      ]
    )

    unpacked_jars(
      name='lib-unpacked-jar',
      libraries=[
        ':lib-source-jar'
      ],
      exclude_patterns=[
        'META-INF/*'
      ],
      intransitive=True,
    )

    jar_library(
      name='lib-source-jar',
      jars=[
        jar(org='{group_id}', name='{artifact_id}', rev='{version}', classifier='sources'),
      ],
      scope='compile',
    )

    jar_library(
      name='lib-binary-jar',
      jars=[
        jar(org='{group_id}', name='{artifact_id}', rev='{version}'),
      ],
      scope='compile',
    )
    """
)


ENTRIES_PATH_RE = re.compile(r"Copied entries to (?P<path>\S+)")


COMPRESSIONS = ("uncompressed", "tar", "zip", "gztar", "bztar")


def index_source_jar(coords, root, compression):
    if compression not in COMPRESSIONS:
        compressions_str = "|".join(COMPRESSIONS)
        raise ToolchainAssertion(f"Invalid compression {compression}, must be one of {compressions_str}")

    coords_relpath_segments = coords.group_id.split(".") + [coords.artifact_id, coords.version]
    dirpath = os.path.join(root, *coords_relpath_segments)
    safe_mkdir(dirpath)
    buildfile = os.path.join(dirpath, "BUILD")
    with open(buildfile, "w") as fp:
        fp.write(
            BUILD_TEMPLATE.format(group_id=coords.group_id, artifact_id=coords.artifact_id, version=coords.version)
        )

    target = f"{dirpath}:lib"
    args = [
        "./pants",
        "index",
        "--no-colors",
        "--resolve-ivy-confs=optional",
        f"--index-bundle-entries-archive={compression}",
        target,
    ]
    with subprocess.Popen(args=args, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
        stdoutdata, stderrdata = proc.communicate()
    if proc.returncode:
        raise ToolchainAssertion(
            f"Indexing source jar for {coords} failed with exit code {proc.returncode}.\n"
            f"STDOUT: {stdoutdata}.\n"
            "\n"
            f"STDERR: {stderrdata}\n"
        )

    mo = ENTRIES_PATH_RE.search(stdoutdata)
    if mo is None:
        raise ToolchainAssertion(f"Could not find entries file path in indexer output {stdoutdata}")
    return mo.group("path")


def main():
    args = sys.argv[1:]
    if len(args) not in (1, 2):
        print(
            textwrap.dedent(
                f"""
                Usage: {sys.argv[0]} <coords> (<dist>)

                coords: <groupId>:<artifactId>:<version>')
                dist:   {'|'.join(COMPRESSIONS)}
                """
            )
        )
        sys.exit(1)

    coords = GAVCoordinates(*args[0].split(":"))
    compression = args[1] if len(args) == 2 else "uncompressed"
    with TemporaryDirectory(dir=".") as root:
        try:
            local_path = index_source_jar(coords, root, compression)
            print(f"Results at: {local_path}")
        except ToolchainError as e:
            print(e)
            sys.exit(1)
