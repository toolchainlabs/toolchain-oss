# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Hashable, Iterable, Iterator, Mapping
from typing import Any, Callable, TypeVar, cast

from toolchain.base.toolchain_error import ToolchainAssertion

K = TypeVar("K", bound=Hashable)
V = TypeVar("V", bound=Hashable)


class FrozenDict(Mapping[K, V]):
    class FreezeError(ToolchainAssertion):
        """Indicates an un-freezable value was encountered."""

        def __init__(self, value: Any) -> None:
            self._value = value
            super().__init__(f"Could not freeze {value} of type {type(value)}.")

        @property
        def value(self) -> Any:
            """The value that was not able to be frozen."""
            return self._value

    @classmethod
    def _freeze_value(cls, value: Any, freezer: Callable[[Any], Hashable] = None) -> Hashable:
        if isinstance(value, Hashable):
            return value
        if isinstance(value, Mapping):
            return cls._freeze_mapping(value, freezer=freezer)
        if freezer:
            return freezer(value)
        raise cls.FreezeError(value)

    @classmethod
    def _freeze_tuple(
        cls, tup: tuple[Any, Any], freezer: Callable[[Any], Hashable] = None
    ) -> tuple[Hashable, Hashable]:
        if len(tup) != 2:
            raise ToolchainAssertion(f"Invalid length: tup={len(tup)}")
        return cls._freeze_value(tup[0], freezer=freezer), cls._freeze_value(tup[1], freezer=freezer)

    @classmethod
    def _freeze_mapping(cls, mapping: Mapping[Any, Any], freezer: Callable[[Any], Hashable] = None) -> FrozenDict:
        return cls(tuple(cls._freeze_tuple(tup, freezer=freezer) for tup in mapping.items()))

    @classmethod
    def freeze_json_obj(cls, obj: Mapping[str, Any]) -> FrozenDict[str, Hashable]:
        """Creates a `FrozenDict` from a JSON object.

        Freezes JSON objects as `FrozenDict` values and JSON arrays as tuples.
        """

        def freeze_list(value: Any) -> Hashable:
            if not isinstance(value, Iterable):
                raise cls.FreezeError(value)
            return tuple(cls._freeze_value(val, freezer=freeze_list) for val in value)

        frozen_json = cls.freeze(obj, freezer=freeze_list)
        return cast(FrozenDict[str, Hashable], frozen_json)

    @classmethod
    def freeze(
        cls,
        item: Mapping[Any, Any] | Iterable[tuple[Any, Any]] | None = None,
        freezer: Callable[[Any], Hashable] = None,
    ) -> FrozenDict[Hashable, Hashable]:
        """Creates a `FrozenDict` by freezing the given item.

        Freezing consists of converting any contained keys or values that are un-hashable (and thus un-frozen), to
        frozen, hashable equivalents. By default just mappings are frozen and all other values are expected to be
        hashable.

        To freeze other value types, a `freezer` function can be passed. The function should return a frozen, hashable
        equivalent for the value it is passed or else raise `FreezeError` if the value cannot be frozen.
        """
        data: OrderedDict[Hashable, Hashable] = OrderedDict()
        if isinstance(item, Mapping):
            data.update(cls._freeze_mapping(item, freezer=freezer))
        elif isinstance(item, Iterable):
            data.update(cls._freeze_tuple(tup, freezer=freezer) for tup in item)
        else:
            raise cls.FreezeError(item)
        return cls(data)

    @classmethod
    def create(cls, **entries: V) -> FrozenDict[str, V]:
        """Creates a `FrozenDict` with string keys derived from keyword argument names."""
        return cls(entries)

    def __init__(self, item: Mapping[K, V] | Iterable[tuple[K, V]] | None = None) -> None:
        """Creates a `FrozenDict` from a mapping object or a sequence of tuples representing entries."""
        data: OrderedDict[K, V] = OrderedDict()
        if item:
            data.update(item)
        self._data = data

    def __getitem__(self, k: K) -> V:
        return self._data[k]

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterator[K]:
        return iter(self._data)

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, FrozenDict) and tuple(self.items()) == tuple(other.items())

    def __hash__(self) -> int:
        return hash(tuple(self.items()))
