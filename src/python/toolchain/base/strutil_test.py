# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.base.strutil import camel_to_dashes


@pytest.mark.parametrize(("camel", "expected_dashes"), [("Foo", "foo"), ("FooBar", "foo-bar"), ("fooBar", "foo-bar")])
def test_camel_to_dashes(camel, expected_dashes):
    assert expected_dashes == camel_to_dashes(camel)
