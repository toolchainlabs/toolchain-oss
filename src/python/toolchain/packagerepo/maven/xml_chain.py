# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).


class XMLChainLink:
    """A link in a 'chain' of XML documents.

    Encapsulates a single XML document (represented by its document element), and a reference to the next link in the
    chain, if any. Element lookups that have no results in the document are delegated to the next link.

    Can be used as a ~drop-in replacement for an xml.etree.Element instance representing a document root, e.g., in
    XMLParsingMixin.

    This allows us to model, e.g., parent-child POM relationships.
    """

    def __init__(self, document_element, next_link=None):
        self._document_element = document_element
        self._next_link = next_link

    def find(self, *args, **kwargs):
        ret = self._document_element.find(*args, **kwargs)
        if ret is None and self._next_link is not None:
            return self._next_link.find(*args, **kwargs)
        return ret

    def findall(self, *args, **kwargs):
        """Aggregates results along the chain.

        POM inheritance is poorly documented, but it appears that this is the correct semantics, otherwise you wouldn't
        be able to inherit common dependencies but also add your own.
        """
        head = self._document_element.findall(*args, **kwargs) or []
        tail = self._next_link.findall(*args, **kwargs) if self._next_link is not None else []
        return head + tail
