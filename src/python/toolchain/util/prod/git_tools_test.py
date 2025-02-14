# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from git import Repo

from toolchain.util.prod.git_tools import get_changed_paths, matched_paths_changed


def test_get_changed_paths(tmp_path) -> None:
    def changed(ref1, ref2):
        return get_changed_paths(ref1, ref2, tmp_path)

    repo = Repo.init(tmp_path)
    index = repo.index
    repo.index.commit("initial commit")

    tf_path = tmp_path / "foo.tf"
    tf_path.touch()
    index.add([str(tf_path)])
    index.commit("a tf change")

    assert ["foo.tf"] == changed("HEAD", "HEAD^")

    py_path = tmp_path / "bar.py"
    py_path.touch()
    index.add([str(py_path)])
    index.commit("a py change")

    assert ["bar.py"] == changed("HEAD", "HEAD^")
    assert ["bar.py", "foo.tf"] == changed("HEAD", "HEAD~2")


def test_matched_paths_changed(tmp_path) -> None:
    def matched_tf(ref1, ref2):
        return matched_paths_changed(r".*\.tf", ref1, ref2, tmp_path)

    repo = Repo.init(tmp_path)
    index = repo.index
    repo.index.commit("initial commit")

    tf_path = tmp_path / "foo.tf"
    tf_path.touch()
    index.add([str(tf_path)])
    index.commit("a tf change")

    assert matched_tf("HEAD", "HEAD^")

    py_path = tmp_path / "bar.py"
    py_path.touch()
    index.add([str(py_path)])
    index.commit("a py change")

    assert not matched_tf("HEAD", "HEAD^")
    assert matched_tf("HEAD", "HEAD~2")

    index.remove([str(tf_path)])
    index.commit("revert a tf change")

    assert matched_tf("HEAD", "HEAD^")
    assert matched_tf("HEAD", "HEAD~2")
    assert not matched_tf("HEAD", "HEAD~3")
