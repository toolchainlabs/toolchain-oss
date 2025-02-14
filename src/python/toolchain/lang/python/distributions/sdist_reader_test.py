# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json
from pathlib import PurePosixPath

import pytest

from toolchain.lang.python.distributions.sdist_reader import PythonSDistReader, SDistReader
from toolchain.lang.python.test_helpers.utils import extract_distribution

_existence_metadata = {
    "home_page": "https://github.com/ckcollab/existence",
    "name": "existence",
    "version": "0.1.3",
    "requires_dist": ["lxml (>=3.3.4)", "cssselect (>=0.9.1)", "progressbar (==2.3)"],
}


_django_metadata = {
    "home_page": "http://www.djangoproject.com/",
    "name": "Django",
    "version": "1.6.11",
    "requires_dist": None,  # It's true! This version of Django has no deps.
}


_requests_metadata = {
    "home_page": "http://python-requests.org",
    "name": "requests",
    "version": "2.22.0",
    "requires_dist": [
        "chardet (<3.1.0,>=3.0.2)",
        "idna (<2.9,>=2.5)",
        "urllib3 (!=1.25.0,!=1.25.1,<1.26,>=1.21.1)",
        "certifi (>=2017.4.17)",
        "pyOpenSSL (>=0.14) ; extra == 'security'",
        "cryptography (>=1.3.4) ; extra == 'security'",
        "idna (>=2.0.0) ; extra == 'security'",
        "PySocks (!=1.5.7,>=1.5.6) ; extra == 'socks'",
        'win-inet-pton ; (sys_platform == "win32" and python_version == "2.7") and extra == \'socks\'',
    ],
}

_qilib_metadata = {
    "home_page": None,
    "name": "qilib",
    "version": "0.3.1",
    "requires_dist": [
        "spirack (>=0.1.8)",
        "numpy",
        "serialize",
        "zhinst",
        "pymongo",
        "requests",
        "qcodes",
        "dataclasses-json",
        "pytest (>=3.3.1) ; extra == 'dev'",
        "coverage (>=4.5.1) ; extra == 'dev'",
        "mongomock ; extra == 'dev'",
    ],
}


_setuptools_metadata = {
    "home_page": "https://pypi.python.org/pypi/setuptools",
    "name": "setuptools",
    "version": "0.7.8",
    "requires_dist": [
        "certifi (==0.0.8) ; extra == 'certs'",
        "ssl (==1.16) ; (python_version in '2.4, 2.5') and extra == 'ssl'",
        "wincertstore (==0.1) ; (sys_platform=='win32') and extra == 'ssl'",
        "ctypes (==1.0.2) ; (sys_platform=='win32' and python_version=='2.4') and extra == 'ssl'",
    ],
}

_raptorq_metadata = {"name": "raptorq", "version": "1.3.1"}


_netuitive_metadata = {"name": "netuitive", "version": "0.1.4"}


_databricks_connect_metadata = {"name": "databricks-connect", "version": "6.3.1"}


_micropython_hashlib5_metadata = {"name": "micropython-hashlib5", "version": "2.4.2.post7"}


_pymasker_metadata = {"name": None, "version": None}

_pyobject_metadata = {"name": "pyobject", "version": "1.2.0"}


@pytest.mark.parametrize(
    ("distribution_name", "expected_content"),
    [
        (
            "requests-2.22.0.tar.gz",
            {
                "requests-2.22.0/LICENSE": "Copyright 2018 Kenneth Reitz",
                "requests-2.22.0/requests/utils.py": "# -*- coding: utf-8 -*-",
            },
        )
    ],
)
def test_open_sdist(distribution_name, expected_content) -> None:
    with extract_distribution(distribution_name) as distribution:
        reader = SDistReader.open_sdist(distribution)
        for relpath, expected_content_prefix in expected_content.items():
            assert reader.read_file(PurePosixPath(relpath)).startswith(expected_content_prefix.encode("utf8"))


def test_get_declared_top_level_modules() -> None:
    reader = PythonSDistReader([PurePosixPath("foo.egg-info/top_level.txt")], lambda path: b"foo\n bar\n  \n\nbaz \n")
    assert {"foo", "bar", "baz"} == reader.get_declared_top_level_modules()


def test_get_py_files() -> None:
    reader = PythonSDistReader(
        [PurePosixPath(p) for p in ["a.txt", "foo/bar.py", "foo/baz/qux.py", "foo/baz/qux.txt"]], lambda x: b""
    )
    assert [PurePosixPath("foo/bar.py"), PurePosixPath("foo/baz/qux.py")] == reader.get_py_files()


@pytest.mark.parametrize(
    ("py_files", "expected_top_level_module_dirs"),
    [
        (["foo/__init__.py", "foo/bar.py", "foo/baz/qux.py"], {"foo"}),
        (["foo/__init__.py", "foo/bar.py", "tests/bar_test.py"], {"foo"}),
        (["lib/foo/__init__.py", "lib/foo/bar.py", "lib/foo/baz/qux.py"], {"lib/foo"}),
        (["lib/foo/__init__.py", "lib/foo/bar.py", "lib2/baz/qux.py"], {"lib/foo", "lib2/baz"}),
    ],
)
def test_detect_top_level_module_dirs(py_files, expected_top_level_module_dirs) -> None:
    def do_test(prefix: str) -> None:
        reader = PythonSDistReader([PurePosixPath(f"{prefix}{file}") for file in py_files], lambda x: b"")
        assert {
            PurePosixPath(f"{prefix}{p}") for p in expected_top_level_module_dirs
        } == reader.detect_top_level_module_dirs()

    # Test normal sdist structure, where everything is under a single top-level dir.
    do_test(prefix="foo-1.2.3/")
    # Test abnormal structures.
    do_test(prefix="")
    do_test(prefix="foo-1.2.3/prefix/")


@pytest.mark.parametrize(
    ("py_files", "declared_top_level_modules", "expected_exported_modules"),
    [
        (["foo/__init__.py", "foo/bar.py", "foo/baz/qux.py"], ["foo"], {"foo", "foo.bar", "foo.baz.qux"}),
        (["foo/__init__.py", "foo/bar.py", "tests/bar_test.py"], ["foo"], {"foo", "foo.bar"}),
        (["foo/__init__.py", "foo/bar.py", "tests/bar_test.py"], None, {"foo", "foo.bar"}),
        (["lib/foo/bar.py", "lib2/foo/__init__.py", "lib2/foo/baz/qux.py"], ["foo"], {"foo", "foo.bar", "foo.baz.qux"}),
        (
            ["lib/a/b.py", "lib/c/d.py", "lib2/e/f.py", "tests/a_test.py"],
            ["a", "c", "e"],
            {"a", "a.b", "c", "c.d", "e", "e.f"},
        ),
    ],
)
def test_get_exported_modules(py_files, declared_top_level_modules, expected_exported_modules) -> None:
    def dummy_reader(path: PurePosixPath):
        if declared_top_level_modules and path.name.endswith("top_level.txt"):
            return b"\n".join(m.encode("utf8") for m in declared_top_level_modules)
        return b""

    files = py_files
    if declared_top_level_modules:
        files += ["foo.egg-info/top_level.txt"]

    def do_test(prefix: str) -> None:
        reader = PythonSDistReader([PurePosixPath(f"{prefix}{file}") for file in files], dummy_reader)
        assert expected_exported_modules == reader.get_exported_modules()

    # Test normal sdist structure, where everything is under a single top-level dir.
    do_test(prefix="foo-1.2.3/")
    # Test abnormal structures.
    do_test(prefix="")


@pytest.mark.parametrize(
    ("distribution_name", "expected_metadata"),
    [
        ("existence-0.1.3.zip", _existence_metadata),
        ("Django-1.6.11.tar.gz", _django_metadata),
        ("requests-2.22.0.tar.gz", _requests_metadata),
        ("qilib-0.3.1.tar.gz", _qilib_metadata),
        ("setuptools-0.7.8.zip", _setuptools_metadata),
        ("raptorq-1.3.1.tar.gz", _raptorq_metadata),  # A rust-cpython sdist.
        ("netuitive-0.1.4.tar.gz", _netuitive_metadata),  # Has a spurious AppleDouble entries with the `._` prefix.
        # SDists with unconventional layouts.
        ("databricks-connect-6.3.1.tar.gz", _databricks_connect_metadata),
        ("micropython-hashlib5-2.4.2.post7.tar.gz", _micropython_hashlib5_metadata),
        ("pymasker-0.2.3.tar.gz", _pymasker_metadata),
        ("pyobject---1.2.0.tar.gz", _pyobject_metadata),
    ],
)
def test_get_metadata(distribution_name, expected_metadata) -> None:
    with extract_distribution(distribution_name) as distribution:
        actual_metadata = SDistReader.open_sdist(distribution).get_metadata()
        # Check just a few keys we care about, so we don't have lots of uninteresting metadata (like description,
        # classifiers and summary) cluttering up the test data above.
        actual_metadata_relevant = {key: actual_metadata.get(key) for key in expected_metadata}
        assert expected_metadata == actual_metadata_relevant
        # Verify that we can serialize the metadata.
        json.dumps(actual_metadata)
