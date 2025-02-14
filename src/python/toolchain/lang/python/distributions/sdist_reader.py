# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import abc
import tarfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Callable, cast

import pkg_resources
import pkginfo
import tomlkit
from wheel.metadata import pkginfo_to_metadata

from toolchain.base.fileutil import temporary_dir
from toolchain.base.memo import memoized_method
from toolchain.base.toolchain_error import ToolchainError
from toolchain.lang.python.util import module_for_file, read_top_level_txt


class SDistError(ToolchainError):
    pass


class SDistReader(abc.ABC):
    """Utility functions for poking around in an sdist.

    There's no canonical way of getting a list of modules and other such info from an sdist, without actually running
    the setup.py, which is A) extremely risky, and B) not always possible (e.g., some old sdists don't run on python3).
    Instead we implement various heuristics here.
    """

    @classmethod
    def open_sdist(cls, path: str):
        """Returns an SDistReader for the sdist at the given path."""
        # based on logic in pkg_info: see https://bazaar.launchpad.net/~tseaver/pkginfo/trunk/revision/184
        if tarfile.is_tarfile(path):
            with tarfile.TarFile.open(path) as trf:
                # PurePosixPath will elide away single dots, e.g., a leading ./, but we must use those unelided
                # names when accessing the tar entries by name, so we retain a map from paths to names.
                path_to_name = {PurePosixPath(info.name): info.name for info in trf.getmembers() if not info.isdir()}
            paths = sorted(path_to_name.keys())

            def read_file(fpath: PurePosixPath):
                with tarfile.TarFile.open(path) as trf:
                    fp = trf.extractfile(path_to_name[fpath])
                    if fp:
                        return fp.read()
                    raise SDistError(f"No entry with path {fpath}")

        elif zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as zpf:
                paths = sorted(PurePosixPath(info.filename) for info in zpf.infolist() if not info.is_dir())

            def read_file(fpath: PurePosixPath):
                with zipfile.ZipFile(path) as zpf:
                    return zpf.read(str(fpath))

        else:
            raise SDistError(f"Not a known sdist format: {path}")

        if not paths:
            raise SDistError(f"No files found in sdist {path}")

        # A root-level Cargo.toml file likely indicates a rust-cpython sdist built with Maturin
        # (https://github.com/PyO3/maturin), which has a very different structure than regular sdists.
        cargo_toml_path = PurePosixPath("Cargo.toml")
        if cargo_toml_path in paths:
            return RustSDistReader(read_file(cargo_toml_path))
        else:
            return PythonSDistReader(sorted(paths), read_file)

    @abc.abstractmethod
    def get_metadata(self) -> dict[str, str]:
        """Get metadata from the sdist, including requirements."""

    @abc.abstractmethod
    def get_exported_modules(self) -> set[str]:
        """Find the modules in the given sdist."""


class PythonSDistReader(SDistReader):
    def __init__(self, paths: list[PurePosixPath], read_file: Callable[[PurePosixPath], bytes]):
        """Do not call directly, except in tests.

        Use SDistReader.open_sdist() instead.
        """
        # Eliminate macOS's AppleDouble paths, which show up, rarely, in sdists (e.g., netuitive-0.1.4).
        self._paths = [path for path in paths if not path.name.startswith("._")]
        self._read_file = read_file

    def read_file(self, file: PurePosixPath) -> bytes:
        return self._read_file(file)

    def extract_file(self, basedir: Path, file: PurePosixPath, coerce_utf8=False) -> Path:
        path = basedir.joinpath(file)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = self.read_file(file)
        if coerce_utf8:
            content = content.decode(errors="ignore").encode()
        path.write_bytes(content)
        return path

    def get_declared_top_level_modules(self) -> set[str] | None:
        """Get the modules listed in the top_level.txt egg-info file, if it exists.

        This file lists the top-level modules officially exported by the sdist.
        """
        return read_top_level_txt(self._paths, self._read_file)

    def _get_egg_info(self, tmpdir: Path) -> Path | None:
        for relpath in self._paths:
            if ".egg-info/" not in str(relpath):
                continue
            # Extract a file under <project>.egg-info/.
            path = self.extract_file(tmpdir, relpath)
            for pt in path.parents:
                # Find the .egg_info dir itself.  Note that we don't rely on it having an entry in the archive.
                if pt.name.endswith(".egg-info"):
                    return pt
        return None

    def _get_pkg_info(self, tmpdir: Path) -> Path | None:
        for relpath in self._paths:
            if relpath.name != "PKG-INFO":
                continue
            # Extract the PKG-INFO file.
            # We've seen cases where the description contains non-utf8 characters, and we
            # don't want to fail metadata conversion for that reason, so we coerce to utf8.
            return self.extract_file(tmpdir, relpath, coerce_utf8=True)
        return None

    def extract_requires_file(self, tmpdir: Path, egg_info: Path) -> None:
        # See: https://github.com/pypa/wheel/blob/a64c6bbcba9bef97a8d1d4ceaaeb8b4854e4f496/src/wheel/metadata.py#L83
        requires_path = PurePosixPath(egg_info.relative_to(tmpdir)) / "requires.txt"
        if requires_path in self._paths:
            self.extract_file(tmpdir, requires_path)

    def get_metadata(self) -> dict[str, str]:
        """Get metadata from the sdist, including requirements."""
        # pkginfo doesn't handle requires.txt in its standard SDist metadata reader.
        # Instead we use a wheel utility function to convert the sdist PKG-INFO file and
        # <project>.egg-info/ directory into wheel metadata, and then read that using pkginfo's
        # Wheel metadata reader.
        with temporary_dir(cleanup=False) as tmpdir_str:
            tmpdir = Path(tmpdir_str)
            # Extract the sdist metadata files needed for the conversion.
            pkg_info = self._get_pkg_info(tmpdir)

            if pkg_info is None:
                return {}

            # Convert the sdist metadata to wheel metadata (this correctly reads requires.txt into Requires-Dist stanzas).
            egg_info = self._get_egg_info(tmpdir)
            if egg_info:
                self.extract_requires_file(tmpdir, egg_info)
            egg_info_path = egg_info or Path("/__nonexistent/")
            try:
                metadata = pkginfo_to_metadata(egg_info_path=egg_info_path.as_posix(), pkginfo_path=pkg_info.as_posix())
            # TODO: Fix once https://github.com/pypa/setuptools/issues/2244 is resolved.
            except (KeyError, pkg_resources.extern.packaging.requirements.InvalidRequirement, UnicodeDecodeError) as e:  # type: ignore
                raise ToolchainError(
                    f"Failed to parse requirement egg_info={egg_info_path.as_posix()} pkg_info={pkg_info.as_posix()}: {e!r}"
                )
            # Write the metadata out so that pkginfo can read it as fake wheel metadata.
            fake_distinfo = tmpdir / "fake.dist-info"
            fake_distinfo.mkdir()
            # Note: metadata is of type email.Message for some reason, and as_string() emits it as expected by Wheel.
            (fake_distinfo / "METADATA").write_bytes(metadata.as_string().encode())
            return vars(pkginfo.Wheel(fake_distinfo.as_posix()))

    @memoized_method
    def get_py_files(self) -> list[PurePosixPath]:
        """Return all .py files."""
        return [name for name in self._paths if name.suffix == ".py"]

    # Ignore these common non-exported top-level modules.
    _ignore_top_level = {"test", "tests", "doc", "docs", "extra", "extras", "example", "examples", "script", "scripts"}

    @memoized_method
    def get_setup_py(self) -> PurePosixPath | None:
        """Find the setup script.

        This is the file named "setup.py" closest to the root. (It is possible for an sdist to contain a regular module
        also named setup.py, and that would be deeper in the file tree).
        """
        return min(
            (py_file for py_file in self.get_py_files() if py_file.name == "setup.py"),
            key=lambda py_file: len(py_file.parts),  # type: ignore
            default=None,
        )

    def detect_top_level_module_dirs(self) -> set[PurePosixPath]:
        """Return the top-level module dirs.

        A well-formed pure python sdist is under a single wrapper dir, e.g., 'foo-1.2.3/'. This is often
        also the package root for py files.  I.e., the top-level modules are usually the direct subdirs of the
        top-level wrapper dir that contain .py files.

        But - this is not always the case! The package root can be under some substructure
        (e.g., a 'src' or 'lib' directory), depending on setup.py's logic, which we cannot run ourselves.

        Also, in some rare cases (e.g., termcolor-1.1.0) the modules are directly under the wrapper dir
        (siblings to setup.py). And in other rare cases (e.g., databricks-connect-6.3.1) there is no
        wrapper dir at all.

        So our heuristic is as follows: assume that the top-level modules are the top-most directories that
        directly contain a .py file (at least an __init__.py), except for the directory containing setup.py.
        If there are no such directories, it means the only modules are the siblings of setup.py.
        """
        # Find all dirs containing python files.
        module_dirs: set[PurePosixPath] = {py_file.parent for py_file in self.get_py_files()}

        # Subtract out the dir containing the setup script.
        setup_py = self.get_setup_py()
        if setup_py:
            module_dirs.remove(setup_py.parent)

        # Now find just the top-level dirs from among those remaining.
        def has_ancestor_in_module_dirs(dr: PurePosixPath) -> bool:
            return any(parent in module_dirs for parent in dr.parents)

        subsumed_module_dirs: set[PurePosixPath] = {d for d in module_dirs if has_ancestor_in_module_dirs(d)}
        top_level_module_dirs: set[PurePosixPath] = module_dirs - subsumed_module_dirs

        return {tlmd for tlmd in top_level_module_dirs if tlmd.name not in self._ignore_top_level}

    def get_exported_modules(self) -> set[str]:
        """Find the modules in the given sdist."""
        # The logic here depends on the interplay between two things:
        #   1. The top-level module dirs we detect (and the modules we discover under them).
        #   2. The top-level modules the sdist declares (if it does so).
        # If there are declared top-level modules, we filter the discovered modules so that we
        # only consider those under the declared top-level modules.
        detected_top_level_module_dirs = self.detect_top_level_module_dirs()
        declared_top_level_modules = self.get_declared_top_level_modules()
        py_files = self.get_py_files()

        # We assume that all declared top-level modules are exported.
        modules = set(declared_top_level_modules or [])

        if detected_top_level_module_dirs:
            # Scan the detected top-level module dirs for modules.
            for top_level_module_dir in detected_top_level_module_dirs:
                top_level_module_name = top_level_module_dir.name
                # If top-level modules were declared, we use them to filter the modules we find by introspection
                # (as those may include tests and other things we don't care about).
                # Otherwise we just take all modules we find.
                if declared_top_level_modules is None or top_level_module_name in declared_top_level_modules:
                    modules.update(self._get_modules(top_level_module_dir, py_files))
        elif not modules:
            # There are no detected or declared top-level module dirs. So the exported modules are
            # just the siblings of the setup.py script.
            setup_py = self.get_setup_py()
            if setup_py:
                modules = {
                    py_file.stem
                    for py_file in py_files
                    if py_file.parent == setup_py.parent
                    and py_file.name != "setup.py"
                    and not py_file.name.startswith("_")
                }

        return modules

    @classmethod
    def _get_modules(cls, top_level_module_dir: PurePosixPath, py_files: list[PurePosixPath]) -> set[str]:
        modules = set()
        package_root_dir = top_level_module_dir.parent
        for py_file in py_files:
            if top_level_module_dir in py_file.parents:
                relpath = py_file.relative_to(package_root_dir)
                if str(relpath) != "setup.py":
                    modules.update(module_for_file(relpath, exportable_only=True))
        return modules


class RustSDistReader(SDistReader):
    """Do not call directly, except in tests.

    Use SDistReader.open_sdist() instead.
    """

    def __init__(self, cargo_toml: bytes) -> None:
        self._cargo = cast(dict, tomlkit.parse(cargo_toml.decode()))

    def _get_path(self, *parts: str):
        current = self._cargo
        for part in parts:
            current = current.get(part, {})
        return current

    def get_metadata(self) -> dict[str, str]:
        """Synthesize metadata for this rust sdist."""
        # In rust-cpython sdists intended to be built by maturin, the python metadata keys live under
        # package.metadata.maturin. See https://github.com/PyO3/maturin for details.
        ret = self._get_path("package", "metadata", "maturin")

        package_name = self.get_package_name()
        if package_name:
            ret["name"] = package_name
        version = self._get_path("package", "version")
        if version:
            ret["version"] = version
        return ret

    def get_exported_modules(self) -> set[str]:
        """Get the single module exported by this rust sdist."""
        # See https://github.com/PyO3/maturin:
        # "The name of the module, which you are using when importing, will be the name value in
        # the [lib] section (which defaults to the name of the package)."
        module = self._get_path("lib", "name") or self.get_package_name()
        return {module} if module else set()

    def get_package_name(self) -> str | None:
        # See https://github.com/PyO3/maturin:
        # "The name of the package will be the name of the cargo project, i.e. the name field in
        # the [package] section of Cargo.toml."
        return self._get_path("package", "name")
