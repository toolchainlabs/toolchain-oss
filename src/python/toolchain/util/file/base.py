# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator

from toolchain.base.toolchain_error import ToolchainAssertion

# Classes to abstract over different file-like stores (currently local filesystem vs. S3).

# Uses the terminology of "file", "path", "directory" etc. for simplicity, and to keep the code easy to
# read and understand, even though S3 uses different terminology ("object", "bucket", "key") and has no
# first-class notion of a "directory".


class FileOrDirectory(ABC):
    @abstractmethod
    def url(self) -> str:
        """Return our URL."""

    @abstractmethod
    def path(self) -> str:
        """Return the path component of our URL.

        Note that these always begin with a forward slash, and use forward slashes as separators.
        """

    @abstractmethod
    def basename(self) -> str:
        """Return the last component of the path."""

    def __str__(self):
        return self.url()

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.url() == other.url()


class File(FileOrDirectory):
    def basename(self) -> str:
        return self.path().rsplit("/", 1)[-1]

    @abstractmethod
    def exists(self) -> bool:
        """Does this file exist?"""

    @abstractmethod
    def get_content(self) -> bytes:
        """Return the content at the URL."""

    @abstractmethod
    def set_content(self, buf: bytes):
        """Set the content at the URL."""

    @abstractmethod
    def delete(self):
        """Delete the file."""

    # Having both copy_to and copy_from allows us to special-case copying between different File subclasses,
    # so that we can perform those operations efficiently, without every subclass having to know about
    # every other subclass (subclasses that don't know how to copy to/from another subclass can delegate
    # to that subclass to copy from/to them).

    @abstractmethod
    def copy_to(self, dst: File):
        """Copy this file to the dst location, overwriting any existing content."""

    @abstractmethod
    def copy_from(self, src: File):
        """Copy the src file to this location, overwriting any existing content."""


class Directory(FileOrDirectory):
    def basename(self) -> str:
        # The last component is the empty string after the trailing slash, we want the component before that.
        return self.path().rsplit("/", 2)[-2]

    def relpath(self, file: File) -> str:
        """Returns the relative path to this directory of the given file, which must be under this directory.

        The returned path is separated with forward slashs on all systems.
        """
        if not file.url().startswith(self.url()):
            raise ToolchainAssertion(f"{file} is not under {self}")
        return file.url()[len(self.url()) :]

    @abstractmethod
    def get_file(self, suffix: str) -> File:
        """Returns a File object under this directory.

        The suffix should be a relative path separated with forward slashes on all systems.
        """

    @abstractmethod
    def traverse(self) -> Iterator[File]:
        """Iterate over all files under the directory, at any depth."""

    @abstractmethod
    def delete(self):
        """Delete the directory and all files in it."""

    def list(self) -> list[File]:
        """List all files under the directory, at any depth."""
        return list(self.traverse())

    def copy_to(self, dst: Directory):
        """Copy this dir to the dst location."""
        for src_file in self.traverse():
            src_file.copy_to(dst.get_file(self.relpath(src_file)))

    def copy_from(self, src: Directory):
        """Copy the src dir to this location."""
        for src_file in src.traverse():
            self.get_file(src.relpath(src_file)).copy_from(src_file)
