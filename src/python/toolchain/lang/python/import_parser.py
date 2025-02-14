# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import ast
import re
import warnings
from functools import cached_property

from toolchain.base.memo import memoized_method
from toolchain.base.toolchain_error import ToolchainAssertion


class ImportParseError(ToolchainAssertion):
    pass


class ImportParser:
    """Parses import statements out of python source code."""

    POSSIBLE_MODULE_REGEX = re.compile(r"^([a-z_][a-z_\d]*\.){2,}[a-zA-Z_]\w*$")

    def __init__(self, module_context: str, source_code: str) -> None:
        self._module_context = module_context
        self._source_code = source_code

    @classmethod
    def is_possible_module(cls, to_match: str) -> bool:
        return bool(cls.POSSIBLE_MODULE_REGEX.match(to_match))

    @cached_property
    def tree(self):
        try:
            return ast.parse(self._source_code)
        except Exception as err:
            raise ImportParseError(f"\nFailed to parse source code:\n{err}")

    @memoized_method
    def collect_imports(self) -> tuple[set[str], set[str]]:
        """Returns a set of all imported symbols."""
        collector = ImportCollector(self._module_context)
        with warnings.catch_warnings():
            # We can see these warnings while parsing code under analysis, and there's no point in displaying them.
            warnings.filterwarnings("ignore", category=DeprecationWarning, message="invalid escape sequence")
            collector.visit(self.tree)
        return collector.imported_symbols, collector.inferred_symbols


class ImportCollector(ast.NodeVisitor):
    def __init__(self, module_context: str) -> None:
        self._module_parts: list[str] = module_context.split(".")
        self.imported_symbols: set[str] = set()
        self.inferred_symbols: set[str] = set()

    def visit_Import(self, node) -> None:
        for alias in node.names:
            self.imported_symbols.add(alias.name)

    def visit_ImportFrom(self, node) -> None:
        rel_module = node.module
        abs_module = ".".join(self._module_parts[0 : -node.level] + ([] if rel_module is None else [rel_module]))
        for alias in node.names:
            self.imported_symbols.add(f"{abs_module}.{alias.name}")

    def visit_Constant(self, node) -> None:
        # Match strings that look like they could be modules.
        if isinstance(node.value, str) and ImportParser.is_possible_module(node.s):
            self.inferred_symbols.add(node.s)
