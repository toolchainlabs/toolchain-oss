# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import sys
from pathlib import Path

import pytest


def run_pytest(test_path: str) -> None:
    tests = Path(test_path)
    if tests.is_file():
        # if a file was passed (because this was called w/ __file__), we want to run all tests in the same dir
        test_path = tests.parent.as_posix()
    pytest_args = [test_path]
    pytest_args.extend(sys.argv[1:])
    pytest_args.append("-vv")
    print(f"Start pytest with {pytest_args}")
    exit_code = pytest.main(pytest_args)
    print(f"pytests finished {exit_code}")
    sys.exit(exit_code)
