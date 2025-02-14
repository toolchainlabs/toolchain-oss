# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.satresolver.test_helpers.pypi_test_data import (
    InterpreterConstraints,
    PlatformConstraints,
    VersionConstraints,
)


@pytest.mark.parametrize(
    ("first", "second", "result"),
    [
        # Both positive
        (PlatformConstraints.requires_linux_x86_64, PlatformConstraints.requires_linux_x86_64, True),
        (PlatformConstraints.requires_linux_x86_64, PlatformConstraints.requires_any, True),
        (PlatformConstraints.requires_any, PlatformConstraints.requires_any, True),
        (PlatformConstraints.requires_any, PlatformConstraints.requires_linux_x86_64, False),
        (PlatformConstraints.requires_linux_x86_64, PlatformConstraints.requires_macosx_10_10_intel, False),
        # Positive, Negative
        (PlatformConstraints.requires_linux_x86_64, PlatformConstraints.excludes_linux_x86_64, False),
        (PlatformConstraints.requires_linux_x86_64, PlatformConstraints.excludes_any, False),
        (PlatformConstraints.requires_any, PlatformConstraints.excludes_any, False),
        (PlatformConstraints.requires_any, PlatformConstraints.excludes_linux_x86_64, False),
        (PlatformConstraints.requires_linux_x86_64, PlatformConstraints.excludes_macosx_10_10_intel, True),
        # Negative, Positive
        (PlatformConstraints.excludes_linux_x86_64, PlatformConstraints.requires_linux_x86_64, False),
        (PlatformConstraints.excludes_linux_x86_64, PlatformConstraints.requires_any, False),
        (PlatformConstraints.excludes_any, PlatformConstraints.requires_any, False),
        (PlatformConstraints.excludes_any, PlatformConstraints.requires_linux_x86_64, False),
        (PlatformConstraints.excludes_linux_x86_64, PlatformConstraints.requires_macosx_10_10_intel, False),
        # Both Negative
        (PlatformConstraints.excludes_linux_x86_64, PlatformConstraints.excludes_any, False),
        (PlatformConstraints.excludes_linux_x86_64, PlatformConstraints.excludes_linux_x86_64, True),
        (PlatformConstraints.excludes_any, PlatformConstraints.excludes_any, True),
        (PlatformConstraints.excludes_any, PlatformConstraints.excludes_linux_x86_64, True),
        (PlatformConstraints.excludes_linux_x86_64, PlatformConstraints.excludes_macosx_10_10_intel, False),
    ],
)
def test_platform_constraint_satisfies(first, second, result):
    assert first.satisfies(second) == result


def test_platform_constraint_lt():
    assert PlatformConstraints.excludes_any < PlatformConstraints.excludes_linux_x86_64
    assert PlatformConstraints.excludes_any < PlatformConstraints.requires_any


def test_python_interpreter_constraint_lt():
    assert InterpreterConstraints.excludes_python < InterpreterConstraints.requires_python
    assert InterpreterConstraints.requires_python_2 < InterpreterConstraints.requires_python_3


@pytest.mark.parametrize(
    ("unsorted_constraints", "sorted_constraints"),
    [
        # All Platform Constraints
        (
            [
                PlatformConstraints.requires_linux_x86_64,
                PlatformConstraints.excludes_any,
                PlatformConstraints.excludes_linux_x86_64,
                PlatformConstraints.requires_macosx_10_10_intel,
                PlatformConstraints.excludes_macosx_10_10_intel,
                PlatformConstraints.requires_any,
            ],
            [
                PlatformConstraints.excludes_any,
                PlatformConstraints.requires_any,
                PlatformConstraints.excludes_linux_x86_64,
                PlatformConstraints.requires_linux_x86_64,
                PlatformConstraints.excludes_macosx_10_10_intel,
                PlatformConstraints.requires_macosx_10_10_intel,
            ],
        ),
        # All InterpreterConstraints
        (
            [
                InterpreterConstraints.requires_python,
                InterpreterConstraints.excludes_python,
                InterpreterConstraints.requires_python_3,
                InterpreterConstraints.requires_python_2,
                InterpreterConstraints.excludes_python_2,
                InterpreterConstraints.excludes_python_3,
            ],
            [
                InterpreterConstraints.excludes_python_2,
                InterpreterConstraints.excludes_python,
                InterpreterConstraints.excludes_python_3,
                InterpreterConstraints.requires_python_2,
                InterpreterConstraints.requires_python,
                InterpreterConstraints.requires_python_3,
            ],
        ),
        # All Version Constraints
        (
            [
                VersionConstraints.requires_aaa_100,
                VersionConstraints.requires_aaa_200,
                VersionConstraints.requires_bbb_100,
                VersionConstraints.excludes_bbb_100,
            ],
            [
                VersionConstraints.requires_aaa_100,
                VersionConstraints.requires_aaa_200,
                VersionConstraints.excludes_bbb_100,
                VersionConstraints.requires_bbb_100,
            ],
        ),
        # Platform constraints, interpreter constraints, version contstraints
        (
            [
                VersionConstraints.requires_aaa_100,
                VersionConstraints.requires_aaa_200,
                VersionConstraints.requires_bbb_100,
                VersionConstraints.excludes_bbb_100,
                InterpreterConstraints.requires_python,
                InterpreterConstraints.excludes_python,
                InterpreterConstraints.requires_python_3,
                InterpreterConstraints.requires_python_2,
                InterpreterConstraints.excludes_python_2,
                InterpreterConstraints.excludes_python_3,
                PlatformConstraints.requires_linux_x86_64,
                PlatformConstraints.excludes_any,
                PlatformConstraints.excludes_linux_x86_64,
                PlatformConstraints.requires_macosx_10_10_intel,
                PlatformConstraints.excludes_macosx_10_10_intel,
                PlatformConstraints.requires_any,
            ],
            [
                PlatformConstraints.excludes_any,
                PlatformConstraints.requires_any,
                PlatformConstraints.excludes_linux_x86_64,
                PlatformConstraints.requires_linux_x86_64,
                PlatformConstraints.excludes_macosx_10_10_intel,
                PlatformConstraints.requires_macosx_10_10_intel,
                InterpreterConstraints.excludes_python_2,
                InterpreterConstraints.excludes_python,
                InterpreterConstraints.excludes_python_3,
                InterpreterConstraints.requires_python_2,
                InterpreterConstraints.requires_python,
                InterpreterConstraints.requires_python_3,
                VersionConstraints.requires_aaa_100,
                VersionConstraints.requires_aaa_200,
                VersionConstraints.excludes_bbb_100,
                VersionConstraints.requires_bbb_100,
            ],
        ),
    ],
)
def test_sorting(unsorted_constraints, sorted_constraints):
    assert sorted_constraints == sorted(unsorted_constraints)
