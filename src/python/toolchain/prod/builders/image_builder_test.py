# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.prod.builders.image_builder import GunicornBuilder, ImageBuilder


def test_django_builder_invalid() -> None:
    with pytest.raises(ImageBuilder.ConfigurationError):
        GunicornBuilder.from_json({"unused": 42})
