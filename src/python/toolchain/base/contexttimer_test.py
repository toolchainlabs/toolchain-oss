# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Based on https://github.com/brouberol/contexttimer/blob/master/tests/test_timer.py with some modifications


import re
from io import StringIO
from unittest import mock

from toolchain.base.contexttimer import Timer, timer


class TestContextTimer:
    def test_timer_print(self):
        def print_reversed(string):
            print(" ".join(reversed(string.split())))

        tests = [
            # (kwargs, expected_regex)
            ({"output": True}, r"took [0-9.]+ seconds"),
            ({"output": print_reversed}, r"seconds [0-9.]+ took"),
            ({"prefix": "foo"}, r"foo took [0-9.]+ seconds"),
            ({"output": True, "prefix": "foo"}, r"foo took [0-9.]+ seconds"),
            # TODO: fix
            # ({"output": True, "fmt": "{} seconds later..."}, r"[0-9.]+ seconds later..."),
        ]

        for kwargs, expected in tests:
            output = StringIO()
            with mock.patch("sys.stdout", new=output), Timer(**kwargs):
                pass
            assert output is not None
            assert re.match(expected, output.getvalue().strip())

    def test_decorator_print(self):
        tests = [
            ({}, r"function foo execution time: [0-9.]+"),
            # TODO: fix
            # ({"fmt": "%(execution_time)s seconds later..."}, r"[0-9.]+ seconds later..."),
        ]

        for kwargs, expected in tests:
            output = StringIO()
            with mock.patch("sys.stdout", new=output):

                @timer(**kwargs)
                def foo():
                    pass

                foo()

            assert output is not None
            assert re.match(expected, output.getvalue().strip())
