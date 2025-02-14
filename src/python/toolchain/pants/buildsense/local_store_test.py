# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json
from pathlib import Path

import pytest

from toolchain.pants.buildsense.local_store import LocalBuildsStore


class TestLocalBuildsStore:
    FAKE_ARTIFACTS = {"new_face": b"pick a face and go with it.", "retail": b"retail is for suckers"}

    def test_store_build(self, tmp_path: Path) -> None:
        store = LocalBuildsStore(tmp_path, 1, True)
        store.store_build("jerry", '{"secret-code": "bosco"}')
        assert (tmp_path / "queue" / "build_stats" / "jerry.json").read_text(
            encoding="utf8"
        ) == '{"secret-code": "bosco"}'

    def test_store_artifacts(self, tmp_path: Path) -> None:
        store = LocalBuildsStore(tmp_path, 1, True)
        store.store_artifacts("pez", artifacts=self.FAKE_ARTIFACTS)
        artifacts = json.loads((tmp_path / "queue" / "artifacts" / "pez.json").read_bytes())

        assert artifacts == {
            "run_id": "pez",
            "artifacts": {
                "new_face": "cGljayBhIGZhY2UgYW5kIGdvIHdpdGggaXQu\n",
                "retail": "cmV0YWlsIGlzIGZvciBzdWNrZXJz\n",
            },
        }

    def _create_builds_in_queue(self, tmp_path: Path, data_type: str):
        upload_dir = tmp_path / "queue"
        if data_type:
            upload_dir = upload_dir / data_type
        if not upload_dir.exists():
            upload_dir.mkdir()
        for fn in ["jerry", "cosmo", "elaine", "george"]:
            (upload_dir / f"{fn}.json").write_text(json.dumps({"secret": "bosco", "name": fn}), encoding="utf8")
        return upload_dir

    def test_store_build_disabled(self, tmp_path: Path) -> None:
        store = LocalBuildsStore(tmp_path, 1, False)
        store.store_build("jerry", '{"secret-code": "bosco"}')
        assert (tmp_path / "queue" / "build_stats" / "jerry.json").exists() is False

    def test_store_artifacts_disabled(self, tmp_path: Path) -> None:
        store = LocalBuildsStore(tmp_path, 1, False)
        store.store_artifacts("pez", artifacts=self.FAKE_ARTIFACTS)
        assert (tmp_path / "queue" / "artifacts" / "pez.json").exists() is False

    def test_get_upload_batch_empty(self, tmp_path: Path) -> None:
        store = LocalBuildsStore(tmp_path, 1, True)
        assert store.get_upload_batch() is None

    @pytest.mark.parametrize("data_type", ["", "build_stats"])
    def test_get_upload_batch_create_new_batch(self, tmp_path: Path, data_type) -> None:
        store = LocalBuildsStore(tmp_path, 1, True)
        upload_dir = self._create_builds_in_queue(tmp_path, data_type)
        assert len(list(upload_dir.iterdir())) == 4
        batch = store.get_upload_batch()
        assert batch is not None
        assert not list(upload_dir.iterdir())
        assert batch.get_metadata() == {"num_of_files": 4, "version": "1"}
        assert json.loads(batch.get_batched_data()) == {
            "version": "1",
            "build_stats": {
                "george": {"secret": "bosco", "name": "george"},
                "elaine": {"secret": "bosco", "name": "elaine"},
                "cosmo": {"secret": "bosco", "name": "cosmo"},
                "jerry": {"secret": "bosco", "name": "jerry"},
            },
        }

    @pytest.mark.parametrize("data_type", ["", "build_stats"])
    def test_get_upload_batch_create_new_batch_max_size(self, tmp_path: Path, data_type) -> None:
        store = LocalBuildsStore(tmp_path, 1, True)
        store._max_batch_size = 100
        upload_dir = self._create_builds_in_queue(tmp_path, data_type)
        assert len(list(upload_dir.iterdir())) == 4
        batch = store.get_upload_batch()

        assert batch is not None
        assert batch.get_metadata() == {"num_of_files": 2, "version": "1"}
        assert {fl.name for fl in upload_dir.iterdir()} == {"elaine.json", "cosmo.json"}
        assert json.loads(batch.get_batched_data()) == {
            "version": "1",
            "build_stats": {
                "george": {"secret": "bosco", "name": "george"},
                "jerry": {"secret": "bosco", "name": "jerry"},
            },
        }

    @pytest.mark.parametrize("data_type", ["", "build_stats"])
    def test_get_upload_batch_existing_batch(self, tmp_path: Path, data_type) -> None:
        store = LocalBuildsStore(tmp_path, 1, True)
        upload_dir = self._create_builds_in_queue(tmp_path, data_type)
        (tmp_path / "upload" / "jerry_batch_1.json").write_text(
            json.dumps(
                {
                    "builds": {
                        "costanza": {"bubble": "boy", "name": "george"},
                        "seinfeld": {"secret": "bosco", "name": "cosmo"},
                        "kramer": {"secret": "bosco", "name": "jerry"},
                    }
                }
            ),
            encoding="utf8",
        )
        assert len(list(upload_dir.iterdir())) == 4
        batch = store.get_upload_batch()
        assert batch is not None
        assert len(list(upload_dir.iterdir())) == 4
        assert batch.get_metadata() == {"num_of_files": 3, "version": "1"}
        assert json.loads(batch.get_batched_data()) == {
            "builds": {
                "costanza": {"bubble": "boy", "name": "george"},
                "seinfeld": {"secret": "bosco", "name": "cosmo"},
                "kramer": {"secret": "bosco", "name": "jerry"},
            }
        }
