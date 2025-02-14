# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from pathlib import PurePosixPath

import pytest
from pkg_resources import Requirement

from toolchain.lang.python.util import (
    find_top_level_txt_file,
    is_exact_requirement,
    is_top_level_txt_file,
    module_for_file,
    parent_module,
)


@pytest.mark.parametrize(
    ("symbol", "expected_parent"),
    [("foo.bar.baz.Baz", "foo.bar.baz"), ("foo.bar.baz", "foo.bar"), ("foo.bar", "foo"), ("foo", "")],
)
def test_parent_module(symbol, expected_parent) -> None:
    assert parent_module(symbol) == expected_parent


@pytest.mark.parametrize("req", ["foo==1.2.3", "bar.baz==2", Requirement.parse("qux==67.8")])
def test_is_exact_requirement(req) -> None:
    assert is_exact_requirement(req)


@pytest.mark.parametrize("req", ["foo>1.2.3", "bar.baz<=2", Requirement.parse("qux")])
def test_is_not_exact_requirement(req) -> None:
    assert not is_exact_requirement(req)


@pytest.mark.parametrize(
    "path",
    [
        "foo-1.2.3.dist-info/top_level.txt",
        "foo-1.2.3.egg-info/top_level.txt",
        "foo-1.2.3/foo-1.2.3.egg-info/top_level.txt",
    ],
)
def test_is_top_level_txt_file(path) -> None:
    assert is_top_level_txt_file(PurePosixPath(path))


@pytest.mark.parametrize(
    "path",
    [
        "foo-1.2.3.dist-info/somthing-else.txt",
        "foo-1.2.3.something-else/top_level.txt",
        "foo/_vendored/wheel/wheel-0.33.6.dist-info/top_level.txt",
    ],
)
def test_is_not_top_level_txt_file(path) -> None:
    assert not is_top_level_txt_file(PurePosixPath(path))


def test_find_top_level_txt_file() -> None:
    assert PurePosixPath("foo-1.2.3.egg-info/top_level.txt") == find_top_level_txt_file(
        [
            PurePosixPath("foo-1.2.3.egg-info/top_level.txt"),
            PurePosixPath("foo/_vendored/wheel/wheel-0.33.6.dist-info/top_level.txt"),
        ]
    )

    assert find_top_level_txt_file([PurePosixPath("foo/_vendored/wheel/wheel-0.33.6.dist-info/top_level.txt")]) is None


@pytest.mark.parametrize(
    ("relpath", "module"),
    [
        ("foo.py", "foo"),
        ("foo/bar.py", "foo.bar"),
        ("foo/bar/baz.py", "foo.bar.baz"),
        ("foo/bar/__init__.py", "foo.bar"),
    ],
)
def test_module_mapper_for_file(relpath: str, module: str) -> None:
    assert {module} == module_for_file(relpath)


def test_module_mapper_for_non_py_file():
    assert set() == module_for_file("foo/bar/baz.txt")
