# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.satresolver.pypi.python_interpreter import PythonInterpreter
from toolchain.satresolver.test_helpers.pypi_test_data import Interpreters


def test_lt() -> None:
    assert Interpreters.python_24 < Interpreters.python_276
    assert Interpreters.python_276 < Interpreters.python_372


def test_gt() -> None:
    assert Interpreters.python_276 > Interpreters.python_24


def test_eq() -> None:
    assert Interpreters.python_24 == PythonInterpreter(interpreter="python", version="2.4")
