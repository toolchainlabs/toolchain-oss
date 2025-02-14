# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).
# Copied from the Pants codebase at 68cd165cbd9f84695753ae7002e98139ab6eb9ff on 6/21/2018, for convenience.

from abc import ABCMeta


class SingletonMetaclass(type):
    """Singleton metaclass."""

    def __call__(cls, *args, **kwargs):
        if not hasattr(cls, "instance"):
            cls.instance = super().__call__(*args, **kwargs)
        return cls.instance


class ClassPropertyDescriptor:
    """Define a readable class property, given a function."""

    # TODO: it seems overriding __set__ and __delete__ would require defining a metaclass or
    # overriding __setattr__/__delattr__ (see
    # https://stackoverflow.com/questions/5189699/how-to-make-a-class-property). The current solution
    # doesn't require any modifications to the class definition beyond declaring a @classproperty.  If
    # we can set __delete__ and have it work, we can use that e.g. to clear the cache for a new
    # `@memoized_classproperty` decorator.
    def __init__(self, fget, doc):
        self.fget = fget
        self.__doc__ = doc

    # See https://docs.python.org/2/howto/descriptor.html for more details.
    def __get__(self, obj, objtype=None):
        if objtype is None:
            objtype = type(obj)
        return self.fget.__get__(obj, objtype)()


def classproperty(func):
    """Use as a decorator on a method definition to make it a class-level attribute.

    This decorator can be applied to a method, a classmethod, or a staticmethod. This decorator will
    bind the first argument to the class object.

    Usage:
    >>> class Foo:
    ...   @classproperty
    ...   def name(cls):
    ...     return cls.__name__
    ...
    >>> Foo.name
    'Foo'

    Setting or deleting the attribute of this name will overwrite this property.

    The docstring of the classproperty `x` for a class `C` can be obtained by
    `C.__dict__['x'].__doc__`.
    """
    doc = func.__doc__

    if not isinstance(func, (classmethod, staticmethod)):
        func = classmethod(func)

    return ClassPropertyDescriptor(func, doc)


def staticproperty(func):
    """Use as a decorator on a method definition to make it a class-level attribute (without binding).

    This decorator can be applied to a method or a staticmethod. This decorator does not bind any
    arguments.

    Usage:
    >>> other_x = 'value'
    >>> class Foo:
    ...   @staticproperty
    ...   def x():
    ...     return other_x
    ...
    >>> Foo.x
    'value'

    Setting or deleting the attribute of this name will overwrite this property.

    The docstring of the classproperty `x` for a class `C` can be obtained by
    `C.__dict__['x'].__doc__`.
    """
    doc = func.__doc__

    if not isinstance(func, staticmethod):
        func = staticmethod(func)

    return ClassPropertyDescriptor(func, doc)


# Extend Singleton and your class becomes a singleton, each construction returns the same instance.
Singleton = SingletonMetaclass("Singleton", (object,), {})


# Abstract base classes w/o __metaclass__ or meta =, just extend AbstractClass.
AbstractClass = ABCMeta("AbstractClass", (object,), {})
