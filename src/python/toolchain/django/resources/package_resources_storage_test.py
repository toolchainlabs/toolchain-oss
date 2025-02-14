# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.django.resources.package_resources_storage import PackageResourcesStorage
from toolchain.django.util import dummy_app


class TestPackageResourcesStorage:
    @pytest.fixture()
    def storage(self):
        return PackageResourcesStorage(dummy_app.__name__, dummy_app.__file__, "static")

    def test_join(self):
        assert PackageResourcesStorage.join("foo", "") == "foo"
        assert PackageResourcesStorage.join("foo/bar", "") == "foo/bar"
        assert PackageResourcesStorage.join("", "baz") == "baz"
        assert PackageResourcesStorage.join("", "baz/qux") == "baz/qux"
        assert PackageResourcesStorage.join("foo", "baz") == "foo/baz"
        assert PackageResourcesStorage.join("foo/bar", "baz") == "foo/bar/baz"
        assert PackageResourcesStorage.join("foo/bar", "baz/qux") == "foo/bar/baz/qux"

    def test_open(self, storage):
        def check(expected_content, path):
            with storage.open(path) as fp:
                content = fp.read().strip()
            assert expected_content == content

        check(b"Foo", "foo.txt")
        check(b"Bar", "subdir/bar.txt")
        check(b"Baz", "subdir/baz.txt")
        check(b"Qux", "subdir/subsubdir/qux.txt")

    def test_exists(self, storage):
        assert storage.exists("subdir/bar.txt")
        assert storage.exists("subdir/subsubdir")
        assert storage.exists("subdir/subsubdir/qux.txt")
        assert not storage.exists("subdir/subsubdi")
        assert not storage.exists("subdir/subsubdirxx")
        assert not storage.exists("subdir/subsubdir/unicorn.txt")

    def test_listdir(self, storage):
        def check(expected_dirs, expected_files, path):
            dirs, files = storage.listdir(path)
            assert len(expected_dirs) == len(dirs)
            assert len(expected_files) == len(expected_files)

        check(["subdir"], ["foo.txt"], "")
        check(["subsubdir"], ["bar.txt", "baz.txt"], "subdir")
        check([], ["qux.txt"], "subdir/subsubdir")
