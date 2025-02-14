# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.packagerepo.pypi.lockfile_parser import parse_lockfile, parse_lockfile_line

_test_data = (
    ("configparser", "4.0.2", "254c1d9c79f60c45dfde850850883d5aaa7f19a23f13561243a050d5a7c3fe4c"),
    ("boto3", "1.9.241", "60e711f1113be926bcec1cfe62fa336438d021ce834f4a5228beead3b4bc5142"),
    ("zope.interface", "4.6.0", "1b3d0dcabc7c90b470e59e38a9acaa361be43b3a6ea644c0063951964717f0e5"),
)


def _convert_line(project_name: str, version: str, sha256: str) -> str:
    return f"{project_name}=={version} --hash=sha256:{sha256}"


@pytest.mark.parametrize(("project_name", "version", "sha256"), _test_data)
def test_parse_lockfile_line(project_name: str, version: str, sha256: str):
    assert (project_name, version, sha256) == parse_lockfile_line(_convert_line(project_name, version, sha256))


def test_parse_lockfile(tmpdir):
    lockfile = tmpdir / "lockfile.txt"
    with open(lockfile, "w") as fp:
        for project_name, version, sha256 in _test_data:
            fp.write(_convert_line(project_name, version, sha256))
            fp.write("\n")
    assert _test_data == tuple(parse_lockfile(lockfile))
