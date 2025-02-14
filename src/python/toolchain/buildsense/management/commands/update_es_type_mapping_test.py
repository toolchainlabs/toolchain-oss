# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.buildsense.management.commands.update_es_type_mapping import Command
from toolchain.buildsense.search.indexes_manager import BuildsenseIndexManager
from toolchain.buildsense.search.indexes_manager_test import load_fixture


@pytest.fixture()
def index_manager(settings) -> BuildsenseIndexManager:
    return BuildsenseIndexManager.for_django_settings(settings)


class FakeCommand(Command):
    def __init__(self, *args, **kwargs):
        self.calls = 0
        self._fixture = kwargs.pop("fixture")
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        raise AssertionError("This code is for unit test only")

    def get_current_mapping(self, mgr):
        self.calls += 1
        return load_fixture(self._fixture)["buildsense"]["mappings"]["run_info"]


def test_get_new_properties(index_manager) -> None:
    cmd = FakeCommand(fixture="mappings_feb_2020")
    new_props = cmd.get_new_properties(index_manager)
    assert "properties" in new_props
    assert cmd.calls == 1
    assert new_props["properties"] == {
        "title": {"type": "text", "fields": {"completion": {"type": "completion"}}},
        "ci_info": {
            "properties": {
                "username": {"type": "keyword"},
                "run_type": {"type": "keyword"},
                "pull_request": {"type": "integer"},
                "job_name": {"type": "keyword"},
                "build_num": {"type": "integer"},
                "build_url": {"type": "text"},
                "link": {"type": "text"},
                "ref_name": {"type": "text"},
            }
        },
        "server_info": {"properties": {"client_ip": {"type": "ip"}}},
    }


def test_get_new_properties_under_nested_type(index_manager) -> None:
    cmd = FakeCommand(fixture="mappings_sep_2020")
    new_props = cmd.get_new_properties(index_manager)
    assert cmd.calls == 1
    assert "properties" in new_props
    assert new_props["properties"] == {
        "title": {"type": "text", "fields": {"completion": {"type": "completion"}}},
        "ci_info": {"properties": {"link": {"type": "text"}, "ref_name": {"type": "text"}}},
        "server_info": {"properties": {"client_ip": {"type": "ip"}}},
    }
