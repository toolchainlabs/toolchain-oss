# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from textwrap import dedent

import pytest

from toolchain.lang.python.import_parser import ImportParser


def test_import_parser():
    import_parser = ImportParser(
        "foo.bar.baz",
        dedent(
            """
            import os
            import os.path
            import requests

            from a.b import c
            from . import qux
            from .x.y import Z
            from ..p import Q

            if os.environ['EXTRA_IMPORTS'] == 1:
                import uu
                from vv import ww

            INFERRED_IMPORTS = [
                # Valid strings
                'a.b.d',
                'a.b2.d',
                'a.b.c.Foo',
                'a.b.c.d.Foo',
                'a.b.c.d.FooBar',
                'a.b.c.d.e.f.g.Baz',
                'a.b_c.d._bar',
                'a.b2.c.D',

                # Invalid strings
                '..a.b.c.d',
                'a.b',
                'a.B.d',
                'a.2b.d',
                'a..b..c',
                'a.b.c.d.2Bar',
                'a.b_c.D.bar',
                'a.b_c.D.Bar',
                'a.2b.c.D',
            ]
            """
        ),
    )

    expected = [
        {"os", "os.path", "requests", "a.b.c", "foo.bar.qux", "foo.bar.x.y.Z", "foo.p.Q", "uu", "vv.ww"},
        {
            "a.b.d",
            "a.b2.d",
            "a.b.c.Foo",
            "a.b.c.d.Foo",
            "a.b.c.d.FooBar",
            "a.b.c.d.e.f.g.Baz",
            "a.b_c.d._bar",
            "a.b2.c.D",
        },
    ]

    imported_symbols, inferred_symbols = import_parser.collect_imports()
    assert expected == [imported_symbols, inferred_symbols]


@pytest.mark.parametrize(
    "module_str",
    ["a.b.d", "a.b2.d", "a.b.c.Foo", "a.b.c.d.Foo", "a.b.c.d.FooBar", "a.b.c.d.e.f.g.Baz", "a.b_c.d._bar", "a.b2.c.D"],
)
def test_is_possible_module_true_for_match(module_str):
    assert ImportParser.is_possible_module(module_str) is True


@pytest.mark.parametrize(
    "module_str",
    ["..a.b.c.d", "a.b", "a.B.d", "a.2b.d", "a..b..c", "a.b.c.d.2Bar", "a.b_c.D.bar", "a.b_c.D.Bar", "a.2b.c.D"],
)
def test_is_possible_module_false_for_no_match(module_str):
    assert ImportParser.is_possible_module(module_str) is False
