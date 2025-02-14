# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from collections.abc import Sequence
from copy import deepcopy

import pytest

from toolchain.base.frozendict import FrozenDict


def assert_empty(frozendict: FrozenDict) -> None:
    assert len(frozendict) == 0
    assert not list(frozendict)
    assert not list(frozendict.keys())
    assert not list(frozendict.items())
    assert not list(frozendict.values())
    assert frozendict == FrozenDict()
    assert hash(frozendict) == hash(FrozenDict())


def test_empty() -> None:
    assert_empty(FrozenDict())


def test_empty_from_mapping() -> None:
    assert_empty(FrozenDict({}))


def test_empty_from_tuples() -> None:
    assert_empty(FrozenDict(()))


def test_nominal() -> None:
    data = {"foo": 42, "bar": frozenset([1, 2, 3]), "baz": (4, 5, 6)}

    def assert_contents(frozendict):
        assert len(data) == len(frozendict)
        assert list(data.keys()) == list(frozendict.keys())
        assert list(data.values()) == list(frozendict.values())
        assert list(data.items()) == list(frozendict.items())
        for k, v in data.items():
            assert v == frozendict[k]

    from_mapping = FrozenDict(data)
    assert_contents(from_mapping)

    from_tuples = FrozenDict((k, v) for k, v in data.items())
    assert_contents(from_tuples)

    assert from_mapping == from_tuples


def test_create() -> None:
    via_create = FrozenDict.create(foo=42, bar=frozenset([1, 2, 3]), baz=(4, 5, 6))
    assert FrozenDict({"foo": 42, "bar": frozenset([1, 2, 3]), "baz": (4, 5, 6)}) == via_create


def test_freeze() -> None:
    def freezer(value):
        if isinstance(value, set):
            return tuple(value)
        raise FrozenDict.FreezeError(value)

    frozendict = FrozenDict.freeze({"foo": 42, "bar": {1, 2, 3}}, freezer=freezer)
    assert FrozenDict.create(foo=42, bar=(1, 2, 3)) == frozendict

    with pytest.raises(FrozenDict.FreezeError):
        FrozenDict.freeze({"foo": 42, "bar": [1, 2, 3]}, freezer=freezer)


def test_freeze_error() -> None:
    with pytest.raises(FrozenDict.FreezeError) as e:
        FrozenDict.freeze({"foo": 42, "bar": {1, 2, 3}})
    exc = e.value
    assert exc.value == {1, 2, 3}


def test_freeze_json_empty() -> None:
    frozendict = FrozenDict.freeze_json_obj({})
    assert frozendict == FrozenDict()


def test_freeze_json() -> None:
    json_obj = {"foo": 42, "bar": [{"baz": [1, 2, 3, {}]}]}

    frozendict = FrozenDict.freeze_json_obj(json_obj)
    assert frozendict["foo"] == 42

    def assert_single_bar_item(mapping):
        bar = mapping["bar"]
        assert isinstance(bar, Sequence)
        assert len(bar) == 1
        return bar[0]

    bar_item = assert_single_bar_item(frozendict)
    assert FrozenDict.create(baz=(1, 2, 3, FrozenDict())) == bar_item

    assert FrozenDict.freeze_json_obj(json_obj) == frozendict

    mutated_shallow = deepcopy(json_obj)
    mutated_shallow["foo"] = 41
    assert FrozenDict.freeze_json_obj(mutated_shallow) != frozendict

    mutated_deep = deepcopy(json_obj)
    mutable_bar_item = assert_single_bar_item(mutated_deep)
    mutable_bar_item["baz"] = [2, 1, 3, {}]
    assert FrozenDict.freeze_json_obj(mutated_deep) != frozendict
