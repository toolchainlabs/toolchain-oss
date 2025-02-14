# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from typing import Callable
from xml.etree import ElementTree

from toolchain.base.toolchain_error import ToolchainError


class XMLParsingError(ToolchainError):
    pass


class XMLParsingMixin:
    """Mixin providing useful utilities for classes that parse XML using xml.etree.

    The utility methods in this mixin allow the caller to deal with paths, tags and text, instead of
    having to know about elements and their methods.

    REMINDER: Mixins must not have an __init__ method, so do not add one to this class.
    """

    # Subclasses can override these (as class or object properties) to provide an XML namespace map
    # (i.e., a map of namespace name to namespace url, as required by various xml.etree methods),
    # and a default namespace name for the document, if any.
    ns_map: dict[str, str] | None = None
    ns: str | None = None

    # Subclasses can override this (per-instance, if necessary) with a callable that
    # takes a single string argument and returns a string to substitute for the given text.
    substitutor: Callable[[str], str] | None = None

    @staticmethod
    def parse(content):
        """Parse the content, returning the root element.

        :param content: bytes representing XML text encoded in some encoding,
                        which the XML parser will detect and decode as appropriate.
        """
        try:
            return ElementTree.fromstring(content)
        except ElementTree.ParseError as e:
            raise XMLParsingError(e)

    @property
    def document_element(self):
        """Subclasses must implement to provide a reference to an XML document's root element."""
        raise NotImplementedError()

    def ns_wrap(self, path):
        """Wrap every path segment in the namespace qualifier.

        Useful when searching for the path in a namespaced document.
        """
        segments = path.split("/")
        ns_segments = [s if (self.ns is None or s.startswith(".")) else f"{self.ns}:{s}" for s in segments]
        return "/".join(ns_segments)

    def text(self, path):
        """Returns the text content of the first element at the given path.

        Returns None if there is no such element, or it contains no text.
        """
        return self._element_text(self._find(path))

    def text_list(self, path):
        """Returns a list of the texts of all elements at the given path."""
        return [self._element_text(e) for e in self._findall(path)]

    def child_text_map(self, parent_path, child_tags):
        """Returns a tag->text map for the children of the first element at the given path."""
        res = self.child_text_maps(parent_path, child_tags)
        return res[0] if res else None

    def child_text_maps(self, parent_path, child_tags):
        """Returns a list of tag->text maps, one per element at the given path."""
        return [{tag: self._child_text(e, tag) for tag in child_tags} for e in self._findall(parent_path)]

    def _find(self, path):
        """Returns the first element at the given path, or None."""
        return self.document_element.find(self.ns_wrap(path), self.ns_map)

    def _findall(self, path):
        """Returns all elements at the given path."""
        return self.document_element.findall(self.ns_wrap(path), self.ns_map)

    def _element_text(self, element):
        """Returns the text of the element, stripped of leading and trailing whitespace.

        Returns an empty string if element is None.
        """
        return "" if element is None else self._substitute(element.text or "").strip()

    def _child_text(self, parent_element, child_tag):
        """Returns the text of the first element with the given tag found under a given element."""
        return self._element_text(parent_element.find(self.ns_wrap(child_tag), self.ns_map))

    def _substitute(self, text):
        """Returns the text, processed by the substitutor if any."""
        if self.substitutor:
            return self.substitutor(text)  # pylint: disable=not-callable
        return text
