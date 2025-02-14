# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from pathlib import PurePosixPath
from typing import Callable, Optional, Union

from pkg_resources import Requirement


def module_for_file(relpath: Union[PurePosixPath, str], exportable_only=False) -> set[str]:
    """Return the (exportable) Python module defined by the given file, if any.

    Returns an empty set if the file doesn't define a module, or a singleton set containing the module name if it does.
    """
    if isinstance(relpath, str):
        relpath = PurePosixPath(relpath)
    if relpath.suffix == ".so":
        # E.g., the module name for foo.cpython-37m-darwin.so is foo.
        # See https://docs.python.org/3/extending/building.html: "the shared library ... must be named
        # after the module name, with an appropriate extension.".
        return {relpath.name.split(".", maxsplit=1)[0]}

    if relpath.suffix != ".py":
        return set()
    module_name_with_slashes = relpath.parent if relpath.name == "__init__.py" else relpath.with_suffix("")
    # We don't consider modules starting with a _, or with a - in the name, exportable.
    if exportable_only and (any(part.startswith("_") or "-" in part for part in module_name_with_slashes.parts)):
        return set()
    module = str(module_name_with_slashes).replace("/", ".")
    return {module}


def parent_module(symbol: str) -> str:
    return symbol.rsplit(".", maxsplit=1)[0] if "." in symbol else ""


def is_top_level_txt_file(name: PurePosixPath) -> bool:
    """Does the name refer to a dist's top_level.txt file."""
    parts = name.parts
    return (
        # In a wheel top_level.txt is always directly under the root-level *.dist-info dir, so len(parts)==2).
        # In an sdist it is in the *.egg-info dir, which is almost always under a top-level wrapper dir,
        # so len(parts) == 3, but we have also encountered a handful of cases without that wrapper dir
        # (so len(parts) == 2). Any top_level.txt deeper than that in the tree is almost certainly due
        # to vendoring of some other dist, and does not pertain to the dist in question.
        len(parts) in [2, 3]
        and parts[-1] == "top_level.txt"
        and parts[-2].endswith((".egg-info", ".dist-info"))
    )


def find_top_level_txt_file(paths: list[PurePosixPath]) -> Optional[PurePosixPath]:
    """Find a dist's top_level.txt file."""
    try:
        return next(path for path in paths if is_top_level_txt_file(path))
    except StopIteration:
        return None


def read_top_level_txt(paths: list[PurePosixPath], get_content: Callable[[PurePosixPath], bytes]) -> Optional[set[str]]:
    """Read the top-level modules from the top_level.txt file, if any.

    names should be a list of names of archive members or files, and get_content a function for reading the content of
    an archive member or file, by its name.
    """
    top_level_txt_file = find_top_level_txt_file(paths)
    if top_level_txt_file:
        return set(filter(None, (x.strip() for x in get_content(top_level_txt_file).decode("utf8").splitlines())))
    return None


def is_exact_requirement(req: Union[str, Requirement]) -> bool:
    if isinstance(req, str):
        req = Requirement.parse(req)
    return len(req.specs) == 1 and req.specs[0][0] == "=="
