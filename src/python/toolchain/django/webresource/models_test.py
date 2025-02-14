# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import gzip
import hashlib

import pytest

from toolchain.django.webresource.models import WebResource


@pytest.mark.parametrize("compressed", [True, False])
def test_content_reader(compressed):
    dummy_text = "Hello, world!"
    dummy_content_uncompressed = dummy_text.encode("utf8")
    dummy_content_compressed = gzip.compress(dummy_content_uncompressed)
    dummy_content = dummy_content_compressed if compressed else dummy_content_uncompressed
    compression = WebResource.GZIP if compressed else WebResource.IDENTITY
    sha256_hexdigest = hashlib.sha256(dummy_content).hexdigest()
    wr = WebResource(
        url="http://dummy.com/dummy",
        sha256_hexdigest=sha256_hexdigest,
        encoding="utf8",
        compression=compression,
        content=dummy_content,
    )
    with wr.content_reader() as cr:
        assert dummy_content_uncompressed == cr.read()

    assert dummy_text == wr.get_content_as_text()
