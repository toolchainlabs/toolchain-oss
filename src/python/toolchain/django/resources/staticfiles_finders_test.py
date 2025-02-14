# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.apps import AppConfig

from toolchain.django.resources.package_resources_storage import PackageResourcesStorage
from toolchain.django.resources.staticfile_finders import AppDirectoriesResourceFinderImpl
from toolchain.django.util import dummy_app


class TestAppDirectoriesResourceFinderImpl:
    def test_get_files(self):
        storage = PackageResourcesStorage(dummy_app.__name__, dummy_app.__file__, "static")
        expected_files = ["foo.txt", "subdir/bar.txt", "subdir/baz.txt", "subdir/subsubdir/qux.txt"]
        files = AppDirectoriesResourceFinderImpl.get_files(storage, "")
        assert len(expected_files) == len(list(files))

    def test_list(self):
        found_files = [x[0] for x in self._create_finder().list(ignore_patterns=[])]
        assert len(["foo.txt", "subdir/bar.txt", "subdir/baz.txt", "subdir/subsubdir/qux.txt"]) == len(found_files) == 4

    def test_find(self):
        finder = self._create_finder()
        path = finder.find("subdir/subsubdir/qux.txt")
        assert path.endswith("toolchain/django/util/dummy_app/static/subdir/subsubdir/qux.txt")

        assert [] == finder.find("subdir/subsubdir/unicorn.txt")

    @staticmethod
    def _create_finder():
        app_config = AppConfig(dummy_app.__name__, dummy_app)
        return AppDirectoriesResourceFinderImpl([app_config])
