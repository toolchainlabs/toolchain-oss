# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.apps import apps
from django.contrib.staticfiles.finders import BaseFinder, searched_locations
from django.contrib.staticfiles.utils import matches_patterns

from toolchain.django.resources.package_resources_storage import PackageResourcesStorage


class AppDirectoriesResourceFinder(BaseFinder):
    """A finder that looks in each app's static files resources dir.

    This has the same functionality as the standard django.contrib.staticfiles.finders.AppDirectoriesFinder,
    but is resource-aware, instead of directly accessing the filesystem.  This allows static resources
    embedded in archives, such as .pex files, to be found.

    We break the actual implementation out into an impl class, so we can test the functionality without
    requiring the Django app registry (which is global state that can only be set up once per process).
    """

    def __init__(self):
        # Django calls this method w/o any args or kwargs
        super().__init__()
        app_configs = apps.get_app_configs()
        self._impl = AppDirectoriesResourceFinderImpl(app_configs)

    def list(self, ignore_patterns):
        return self._impl.list(ignore_patterns)

    def find(self, path, all=False):
        return self._impl.find(path, all)


class AppDirectoriesResourceFinderImpl:
    """Implements AppDirectoriesResourceFinder functionality without requiring the Django apps registry.

    Separated out for testability.
    """

    storage_class = PackageResourcesStorage
    source_dir = "static"

    @classmethod
    def get_files(cls, storage, ignore_patterns=None, path=""):
        """Recursively walk the storage directories yielding the paths of all files that should be copied.

        Modeled on django.contrib.staticfiles.utils.get_files, but uses
        PackageResourcesStorage.join instead of os.path.join.

        :param PackageResourcesStorage storage: The storage system to walk.
        :param ignore_patterns: Ignore files that match any of these patterns.
        :param path: The directory to walk.
        """
        if ignore_patterns is None:
            ignore_patterns = []
        directories, files = storage.listdir(path)
        for fn in files:
            if not matches_patterns(fn, ignore_patterns):
                yield storage.join(path, fn)
        for dn in directories:
            if not matches_patterns(dn, ignore_patterns):
                yield from cls.get_files(storage, ignore_patterns, storage.join(path, dn))

    def __init__(self, app_configs):
        self.apps = []
        self.storages = {}
        for app_config in app_configs:
            self.storages[app_config.name] = self.storage_class(
                app_config.module.__name__, app_config.path, self.source_dir
            )
            if app_config.name not in self.apps:
                self.apps.append(app_config.name)

    # Implementation of the BaseFinder abstract methods.
    # Modeled on the implementations in django.contrib.staticfiles.finders.AppDirectoriesFinder.
    # Sadly, although that finder does use the Storage abstraction, it implicitly assumes that the
    # storages are of class FileSystemStorage.
    # TODO: Contribute a refactor to the standard Django class, to make it truly work with other storages?
    def list(self, ignore_patterns):
        for storage in self.storages.values():
            for path in self.get_files(storage, ignore_patterns):
                yield path, storage

    def find(self, path, all=False):
        matches = []
        for app in self.apps:
            app_location = self.storages[app].location
            # The findstatic command uses the global searched_locations to print the list of searched locations.
            # This is an example of where Django's staticfiles functionality implicitly assumes a FileSystemStorage:
            # The "location" concept is specific to FileSystemStorage, and not part of the Storage interface.
            # However since "location" in this context is only used for end-user display, it just needs to be
            # human-readable, and not something you can actually use to find a resource.
            if app_location not in searched_locations:
                searched_locations.append(app_location)
            match = self._find_in_app(app, path)
            if match:
                if not all:
                    return match
                matches.append(match)
        return matches

    def _find_in_app(self, app, path):
        """Find a requested static file in an app's static resources."""
        storage = self.storages.get(app)
        # Only try to find a file if the source dir actually exists.
        if not storage or not storage.exists(path):
            return None
        return storage.path(path) or None
