# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime
import json
from enum import Enum

import pkg_resources
import pytest

from toolchain.buildsense.records.run_info import RunInfo
from toolchain.buildsense.search.es_config import BuildSenseElasticSearchConfig
from toolchain.buildsense.search.indexes_manager import BuildsenseIndexManager
from toolchain.util.test.elastic_search_util import DummyElasticRequests


def load_fixture(fixture: str) -> dict:
    return json.loads(pkg_resources.resource_string(__name__, f"fixtures/{fixture}.json"))


class TestBuildsenseIndexManager:
    _ES_TYPES_MAP = {
        str: ["text", "keyword", "ip"],
        Enum: ["keyword"],
        int: ["integer"],
        datetime.datetime: ["date"],
        datetime.timedelta: ["integer"],
    }

    @pytest.fixture()
    def index_mgr(self, settings) -> BuildsenseIndexManager:
        DummyElasticRequests.reset()
        cfg = BuildSenseElasticSearchConfig.for_tests(DummyElasticRequests.factory, indices_names=("buildsense-v1",))
        return BuildsenseIndexManager(es_cfg=cfg)

    def test_get_current_mapping(self, index_mgr: BuildsenseIndexManager) -> None:
        mapping_fixture = load_fixture("mappings_sep_2020")["buildsense"]["mappings"]["run_info"]
        DummyElasticRequests.add_response(
            method="GET",
            url="/buildsense-v1/_mapping",
            json_body={"buildsense-v1": {"mappings": mapping_fixture}},
        )
        current_mapping = index_mgr.get_current_mapping()
        assert len(DummyElasticRequests.get_requests()) == 1
        assert set(current_mapping["properties"].keys()) == {
            "branch",
            "buildroot",
            "ci_info",
            "cmd_line",
            "computed_goals",
            "customer_id",
            "default_report",
            "machine",
            "outcome",
            "path",
            "repo_id",
            "report_url",
            "revision",
            "run_id",
            "run_time",
            "server_info",
            "specs_from_command_line",
            "timestamp",
            "user_api_id",
            "version",
        }

    def test_mapping(self, index_mgr: BuildsenseIndexManager) -> None:
        def _get_mapped_props(props):
            mapped_props = {}
            for name, prop in props.items():
                if "properties" in prop:
                    # nested structure, like server_info
                    mapped_props[name] = _get_mapped_props(prop["properties"])
                else:
                    mapped_props[name] = prop["type"]
            return mapped_props

        def _get_type(field_type):
            if field_type in self._ES_TYPES_MAP:
                return field_type
            # for now we only support Optional[x] here and we will
            # return x. i.e. for Optional[str] we will return str
            if field_type.__module__ == "typing":
                return field_type.__args__[0]
            if issubclass(field_type, Enum):
                return Enum
            raise AssertionError(f"Unknown field_type: {field_type}")

        def _check_fields(fields_dict, es_dict):
            seen = set()
            for name, field in fields_dict.items():
                if isinstance(field, dict):
                    assert name in es_dict
                    assert isinstance(es_dict[name], dict)
                    _check_fields(field, es_dict[name])
                    seen.add(name)
                elif field.type is dict:
                    assert name not in es_dict
                else:
                    seen.add(name)
                    assert name in es_dict
                    expected_type = self._ES_TYPES_MAP[_get_type(field.type)]
                    assert es_dict[name] in expected_type
            assert seen - set(es_dict.keys()) == set()

        prop_map = index_mgr.load_mappings()["properties"]
        es_map = _get_mapped_props(prop_map)
        _check_fields(RunInfo.get_fields(), es_map)

    def test_create_index_existing(self, index_mgr: BuildsenseIndexManager) -> None:
        DummyElasticRequests.add_response(method="HEAD", url="/buildsense-v1")
        assert index_mgr.create_index() is False
        assert len(DummyElasticRequests.get_requests()) == 1

    def test_create_index_and_new_alias(self, index_mgr: BuildsenseIndexManager) -> None:
        DummyElasticRequests.add_response(method="HEAD", url="/buildsense-v1", status_code=404)
        DummyElasticRequests.add_response(method="PUT", url="/buildsense-v1")
        DummyElasticRequests.add_response(method="HEAD", url="/_alias/buildsense", status_code=404)
        DummyElasticRequests.add_response(method="PUT", url="/buildsense-v1/_alias/buildsense")
        assert index_mgr.create_index() is True
        assert len(DummyElasticRequests.get_requests()) == 4

    def test_create_new_index(self) -> None:
        DummyElasticRequests.reset()
        cfg = BuildSenseElasticSearchConfig.for_tests(
            DummyElasticRequests.factory, indices_names=("buildsense-v1", "buildsense-v2")
        )
        DummyElasticRequests.add_response(method="HEAD", url="/buildsense-v2", status_code=404)
        DummyElasticRequests.add_response(method="PUT", url="/buildsense-v2")
        DummyElasticRequests.add_response(method="POST", url="/_reindex", json_body=load_fixture("es_reindex_response"))
        index_mgr = BuildsenseIndexManager(es_cfg=cfg)
        assert index_mgr.create_index() is True
        requests = DummyElasticRequests.get_requests()
        assert len(requests) == 3
        reindex_request = requests[-1]
        assert reindex_request.url == "/_reindex"
        assert reindex_request.get_json_body() == {
            "dest": {"index": "buildsense-v2"},
            "source": {"index": "buildsense-v1"},
        }
