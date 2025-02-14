# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pkg_resources
from django.core.files import File
from django.core.files.storage import Storage

from toolchain.base.toolchain_error import ToolchainAssertion


class PackageResourcesStorage(Storage):
    """A Django storage system that reads from package resources.

    This storage is read-only.  All write operations will fail.
    """

    @staticmethod
    def join(left, right):
        # Note that resource paths always use forward slashes, not os.path.sep.
        return left if not right else right if not left else f"{left}/{right}"

    def __init__(self, package_name, package_path, base_dir=""):
        """
        :param package_name: The name of the package to read resources from, e.g., foo.bar.baz.
        :param package_path: The filesystem path to this package dir.  If the package is an unpacked dir
                             this should be the full path to that dir, e.g., /path/to/foo/bar/baz.
                             If the package is embedded in an archive file, this should be the full path to that file,
                             suffixed with the relative path to the package, e.g., /path/to/archive.pex/foo/bar/baz.
                             Note that AppConfig.path will compute this path for a package containing a Django app.
        :param base_dir: A base relpath to prepend to all names read from the package. Must use
                         forward slashes as path separators on all systems.
        """
        self._package_name = package_name
        if base_dir.startswith("/"):
            raise ToolchainAssertion("base_dir must be a relative resource directory path.")
        self._base_dir = base_dir
        self._location = self.join(package_path, self._base_dir)

    def location(self):
        """A human-readable representation of this storage's location.

        Not used for actually addressing resources.
        """
        return self._location

    # Base class method implementations.
    def _open(self, name, mode="rb"):
        if mode != "rb":
            raise ToolchainAssertion("Only rb mode supported for open()")
        return File(pkg_resources.resource_stream(self._package_name, self._full_name(name)))

    def save(self, name, content, max_length=None):
        raise self._read_only_error()

    def get_available_name(self, name, max_length=None):
        raise self._read_only_error()

    def generate_filename(self, filename):
        raise self._read_only_error()

    def path(self, name):
        # NB: The Django documentation for Storage.path() states that "Storage systems that can't be
        # accessed using open() should *not* implement this method."  So we shouldn't be implementing it.
        # However the collectstatic command in copy mode currently calls path() on the storage system,
        # just for logging (it doesn't attempt to open() the resulting path). In symlink mode collectstatic *does*
        # attempt to use the resulting path as a symlink source, but we don't expect symlinking to work
        # with this storage system anyway, at least when used against an archive.
        # Unless/until we contribute a patch to Django to finesse this, we implement path(), so that
        # collectstatic against this storage will work, and log something useful.
        # In fact, if run against an unpacked directory, path() will return the real filesystem dir,
        # so even symlinking, in that case, will work.
        return self.join(self._location, name)

    def delete(self, name):
        raise self._read_only_error()

    def exists(self, name):
        return pkg_resources.resource_exists(self._package_name, self._full_name(name))

    def listdir(self, path):
        directories = []
        files = []
        if self.exists(path):
            for entry_name in pkg_resources.resource_listdir(self._package_name, self._full_name(path)):
                if pkg_resources.resource_isdir(self._package_name, self._full_name(self.join(path, entry_name))):
                    directories.append(entry_name)
                else:
                    files.append(entry_name)
        return directories, files

    def size(self, name):
        raise self._not_supported_error("size()")

    def url(self, name):
        raise self._not_supported_error("url()")

    def get_accessed_time(self, name):
        raise self._not_supported_error("get_access_time()")

    def get_created_time(self, name):
        raise self._not_supported_error("get_created_time()")

    def get_modified_time(self, name):
        raise self._not_supported_error("get_modified_time()")

    def _full_name(self, name):
        return self.join(self._base_dir, name)

    @classmethod
    def _read_only_error(cls):
        return NotImplementedError(
            f"{cls.__name__} is a read-only storage system and does not support write operations."
        )

    @classmethod
    def _not_supported_error(cls, operation):
        return NotImplementedError(f"The {cls.__name__} storage system does not support {operation}.")
