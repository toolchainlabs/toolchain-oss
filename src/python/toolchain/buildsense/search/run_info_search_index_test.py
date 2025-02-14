# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import uuid

import pytest
from django.conf import settings
from opensearchpy import ConnectionError, TransportError

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.buildsense.records.run_info import RunInfo, ServerInfo
from toolchain.buildsense.search.run_info_search_index import FieldsMap, RunInfoSearchIndex, SearchTransientError
from toolchain.buildsense.test_utils.data_loader import parse_run_info
from toolchain.buildsense.test_utils.fixtures_loader import load_fixture
from toolchain.django.site.models import Customer, Repo, ToolchainUser
from toolchain.util.test.elastic_search_util import DummyElasticRequests


@pytest.mark.django_db()
class TestRunInfoSearchIndex:
    def _get_base_query(
        self, server_env="test", customer_id="yadayada", page_size=10, sort="-timestamp", offset: int | None = None
    ):
        sort = {sort.strip("-"): {"order": "desc"}} if sort.startswith("-") else sort
        base_query = {
            "query": {
                "bool": {
                    "must": [{"term": {"server_info.environment": server_env}}, {"term": {"customer_id": customer_id}}]
                }
            },
            "size": page_size,
            "sort": [sort, {"server_info.accept_time": {"order": "desc"}}, "_id"],
        }
        if offset:
            base_query["from"] = offset
        return base_query

    @pytest.fixture()
    def search_idx(self) -> RunInfoSearchIndex:
        DummyElasticRequests.reset()
        return RunInfoSearchIndex.for_customer_id(settings, "yadayada")

    def _get_run_infos(self, user: ToolchainUser, repo: Repo) -> list[RunInfo]:
        base_time = datetime.datetime(2019, 4, 22, 19, 28, 52, tzinfo=datetime.timezone.utc)
        server_info = ServerInfo(
            request_id=str(uuid.uuid4()),
            accept_time=base_time,
            stats_version="1",
            environment="bisque-soup",
            s3_bucket="fake-bucket",
            s3_key="fake-key",
        )
        base_time = base_time or utcnow()
        build_time = base_time
        run_infos = []
        for fixture_id in range(1, 7):
            build_data = load_fixture(f"sample{fixture_id}")
            build_data["run_info"]["timestamp"] = int(build_time.replace(tzinfo=datetime.timezone.utc).timestamp())
            run_info = parse_run_info(fixture_data=build_data, repo=repo, user=user, server_info=server_info)
            build_time = build_time + datetime.timedelta(minutes=12)
            run_infos.append(run_info)
        return run_infos

    def test_bad_search_invalid_times(self, search_idx: RunInfoSearchIndex) -> None:
        with pytest.raises(ToolchainAssertion, match="Earliest date is after latest date."):
            search_idx.search_all_matching(
                repo_id="uncle-leo",
                field_map={"cmd_line": "bania!"},
                earliest=datetime.datetime(2019, 11, 27, tzinfo=datetime.timezone.utc),
                latest=datetime.datetime(2019, 8, 1, tzinfo=datetime.timezone.utc),
                page_size=20,
            )

    def test_search_invalid_field(self, search_idx: RunInfoSearchIndex) -> None:
        with pytest.raises(ToolchainAssertion, match="Queries not allowed for field: foo."):
            search_idx.search_all_matching(repo_id="uncle-leo", field_map={"foo": "bar"}, page_size=20)

    def test_search_multiple_fields(self, search_idx: RunInfoSearchIndex) -> None:
        DummyElasticRequests.add_empty_search_response()
        results = search_idx.search_all_matching(
            repo_id="uncle-leo",
            field_map={"branch": "ovaltine", "cmd_line": "spongebob"},
            page_size=18,
            sort="timestamp",
        )
        assert results.total_count == 0
        assert len(results.items) == 0
        expected = self._get_base_query(page_size=18, sort="timestamp")
        expected["query"]["bool"]["must"].extend(
            [
                {"term": {"repo_id": "uncle-leo"}},
                {"match": {"branch": "ovaltine"}},
                {"match": {"cmd_line": "spongebob"}},
            ]
        )
        assert DummyElasticRequests.get_request().get_json_body() == expected

    def test_search_by_goals(self, search_idx: RunInfoSearchIndex) -> None:
        DummyElasticRequests.add_empty_search_response()
        results = search_idx.search_all_matching(
            repo_id="uncle-leo",
            field_map={"goals": ["ovaltine", "roundtine"], "outcome": "NEWMAN"},
            page_size=18,
            sort="timestamp",
        )
        assert results.total_count == 0
        assert len(results.items) == 0
        expected = self._get_base_query(page_size=18, sort="timestamp")
        expected["query"]["bool"]["must"].extend([{"term": {"repo_id": "uncle-leo"}}, {"term": {"outcome": "NEWMAN"}}])
        expected["query"]["bool"].update(
            {
                "minimum_should_match": 1,
                "should": [
                    {"match_phrase": {"computed_goals": "ovaltine"}},
                    {"match_phrase": {"computed_goals": "roundtine"}},
                ],
            }
        )
        assert DummyElasticRequests.get_request().get_json_body() == expected

    def test_search_by_goal(self, search_idx: RunInfoSearchIndex) -> None:
        DummyElasticRequests.add_empty_search_response()
        results = search_idx.search_all_matching(
            repo_id="uncle-leo", field_map={"goals": "ovaltine", "branch": "chicken"}, page_size=18, sort="timestamp"
        )
        assert results.total_count == 0
        assert len(results.items) == 0
        expected = self._get_base_query(page_size=18, sort="timestamp")
        expected["query"]["bool"]["must"].extend(
            [
                {"term": {"repo_id": "uncle-leo"}},
                {"match": {"branch": "chicken"}},
                {"match_phrase": {"computed_goals": "ovaltine"}},
            ]
        )
        assert DummyElasticRequests.get_request().get_json_body() == expected

    def test_search_multiple_fields_with_runtime_sort(self, search_idx: RunInfoSearchIndex) -> None:
        DummyElasticRequests.add_empty_search_response()
        results = search_idx.search_all_matching(
            repo_id="uncle-leo",
            field_map={"branch": "ovaltine", "cmd_line": "spongebob"},
            page_size=18,
            sort="-run_time",
        )
        assert results.total_count == 0
        assert len(results.items) == 0
        expected = self._get_base_query(page_size=18, sort="-run_time")
        expected["query"]["bool"]["must"].extend(
            [
                {"term": {"repo_id": "uncle-leo"}},
                {"match": {"branch": "ovaltine"}},
                {"match": {"cmd_line": "spongebob"}},
            ]
        )
        assert DummyElasticRequests.get_request().get_json_body() == expected

    def test_search_multiple_fields_with_range(self, search_idx: RunInfoSearchIndex) -> None:
        DummyElasticRequests.add_empty_search_response()
        results = search_idx.search_all_matching(
            repo_id="uncle-leo",
            field_map={"branch": "ovaltine"},
            earliest=datetime.datetime(2019, 1, 31, 19, 44, 55, tzinfo=datetime.timezone.utc),
            latest=datetime.datetime(2019, 5, 20, 2, 19, 10, tzinfo=datetime.timezone.utc),
            page_size=12,
        )
        assert results.total_count == 0
        assert len(results.items) == 0
        expected = self._get_base_query(page_size=12)
        expected["query"]["bool"]["must"].extend(
            [
                {"term": {"repo_id": "uncle-leo"}},
                {"range": {"timestamp": {"format": "epoch_second", "gte": 1548963895, "lte": 1558318750}}},
                {"match": {"branch": "ovaltine"}},
            ]
        )
        assert DummyElasticRequests.get_request().get_json_body() == expected

    def test_search_by_run_time(self, search_idx: RunInfoSearchIndex) -> None:
        DummyElasticRequests.add_empty_search_response()
        results = search_idx.search_all_matching(
            repo_id="uncle-leo",
            field_map={"goals": "test", "run_time": (datetime.timedelta(seconds=5.8), datetime.timedelta(minutes=4))},
            earliest=datetime.datetime(2019, 1, 31, 19, 44, 55, tzinfo=datetime.timezone.utc),
            latest=datetime.datetime(2019, 5, 20, 2, 19, 10, tzinfo=datetime.timezone.utc),
            page_size=12,
        )
        assert results.total_count == 0
        assert len(results.items) == 0
        expected = self._get_base_query(page_size=12)
        expected["query"]["bool"]["must"].extend(
            [
                {"term": {"repo_id": "uncle-leo"}},
                {"range": {"timestamp": {"format": "epoch_second", "gte": 1548963895, "lte": 1558318750}}},
                {"match_phrase": {"computed_goals": "test"}},
                {"range": {"run_time": {"gte": 5_800, "lte": 240_000}}},
            ]
        )
        assert DummyElasticRequests.get_request().get_json_body() == expected

    def test_search_single_field(self, search_idx: RunInfoSearchIndex) -> None:
        user = ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")
        customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        customer.add_user(user)
        repo = Repo.create("kramer", customer=customer, name="Jerry Seinfeld is a funny guy")
        run_infos = self._get_run_infos(user, repo)
        DummyElasticRequests.add_search_response(run_infos, override_total=882)
        results = search_idx.search_all_matching(
            repo_id="uncle-leo",
            field_map={"branch": "ovaltine"},
            sort="-run_time",
            page_size=12,
        )
        assert results.total_count == 882
        run_keys = results.items
        assert len(run_keys) == 6
        for rk in run_keys:
            assert rk.repo_id == repo.pk
            assert rk.user_api_id == user.api_id
        assert run_keys[0].run_id == "pants_run_2018_06_15_16_04_22_681_b9222bfce9cd421ba1a67ec225a8c6f6"
        assert run_keys[3].run_id == "pants_run_2019_07_19_15_35_18_154_36abaf9ca0894265828d66e1bae1a969"
        expected = self._get_base_query(page_size=12, sort="-run_time")
        expected["query"]["bool"]["must"].extend(
            [{"term": {"repo_id": "uncle-leo"}}, {"match": {"branch": "ovaltine"}}]
        )
        assert DummyElasticRequests.get_request().get_json_body() == expected

    def test_search_with_term(self, search_idx: RunInfoSearchIndex) -> None:
        DummyElasticRequests.add_empty_search_response()
        search_idx.search_all_matching(
            repo_id="uncle-leo", field_map={"cmd_line": "puffy", "outcome": "ABORTED"}, page_size=16
        )
        expected = self._get_base_query(page_size=16)
        expected["query"]["bool"]["must"].extend(
            [{"term": {"repo_id": "uncle-leo"}}, {"match": {"cmd_line": "puffy"}}, {"term": {"outcome": "ABORTED"}}]
        )
        assert DummyElasticRequests.get_request().get_json_body() == expected

    def test_search_field_exists(self, search_idx: RunInfoSearchIndex) -> None:
        DummyElasticRequests.add_empty_search_response()
        search_idx.search_all_matching(repo_id="uncle-leo", field_map={"ci": True, "outcome": "ABORTED"}, page_size=15)

        expected = self._get_base_query(page_size=15)
        expected["query"]["bool"]["must"].extend(
            [{"term": {"repo_id": "uncle-leo"}}, {"exists": {"field": "ci_info"}}, {"term": {"outcome": "ABORTED"}}]
        )

        assert DummyElasticRequests.get_request().get_json_body() == expected

    def test_search_field_doesnt_exists(self, search_idx: RunInfoSearchIndex) -> None:
        DummyElasticRequests.add_empty_search_response()
        search_idx.search_all_matching(repo_id="uncle-leo", field_map={"ci": False, "outcome": "FAIL"}, page_size=28)
        expected = self._get_base_query(page_size=28)
        expected["query"]["bool"]["must"].extend([{"term": {"repo_id": "uncle-leo"}}, {"term": {"outcome": "FAIL"}}])
        expected["query"]["bool"]["must_not"] = [{"exists": {"field": "ci_info"}}]
        assert DummyElasticRequests.get_request().get_json_body() == expected

    def test_search_unsupported_list_of_values(self, search_idx: RunInfoSearchIndex) -> None:
        DummyElasticRequests.add_empty_search_response()
        with pytest.raises(ToolchainAssertion, match="List of values not supported with field: outcome"):
            search_idx.search_all_matching(
                repo_id="uncle-leo", field_map={"cmd_line": "puffy", "outcome": ["ABORTED"]}, page_size=23
            )
        DummyElasticRequests.assert_no_requests()

    def test_exceed_max_page_size(self, search_idx: RunInfoSearchIndex) -> None:
        DummyElasticRequests.add_empty_search_response()
        with pytest.raises(ToolchainAssertion, match="Max page size exceeded."):
            search_idx.search_all_matching(repo_id="uncle-leo", field_map={"branch": "ovaltine"}, page_size=80)
        DummyElasticRequests.assert_no_requests()

    def test_str(self, search_idx: RunInfoSearchIndex) -> None:
        assert str(search_idx) == "RunInfoSearchIndex(environment=test index=buildsense customer_id=yadayada)"

    def test_get_for_run_id(self, search_idx: RunInfoSearchIndex) -> None:
        user = ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")
        customer = Customer.create(slug="yada", name="Yada Yada")
        repo = Repo.create("pez", customer=customer, name="Jerry Seinfeld is a funny guy")
        run_info = self._get_run_infos(user, repo)[3]
        DummyElasticRequests.add_search_response([run_info])
        run_key = search_idx.get_for_run_id(repo_id="puffy-shirt", run_id="cartwright")
        request = DummyElasticRequests.get_request()
        assert request.get_json_body() == {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": "yadayada"}},
                        {"term": {"repo_id": "puffy-shirt"}},
                        {"term": {"run_id": "cartwright"}},
                    ]
                }
            }
        }
        assert run_key is not None
        assert run_key.user_api_id == user.api_id
        assert run_key.run_id == "pants_run_2019_07_19_15_35_18_154_36abaf9ca0894265828d66e1bae1a969"
        assert run_key.repo_id == repo.pk

    def test_get_for_run_id_empty(self, search_idx: RunInfoSearchIndex) -> None:
        DummyElasticRequests.add_empty_search_response()
        run_key = search_idx.get_for_run_id(repo_id="jerk-store", run_id="festivus")
        assert run_key is None
        request = DummyElasticRequests.get_request()
        assert request.get_json_body() == {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": "yadayada"}},
                        {"term": {"repo_id": "jerk-store"}},
                        {"term": {"run_id": "festivus"}},
                    ]
                }
            }
        }

    def test_get_possible_values_for_fields_outcome(self, search_idx: RunInfoSearchIndex) -> None:
        DummyElasticRequests.add_aggregation_response(index="buildsense", results=(("outcome", ["SUCCESS", "FAIL"]),))
        values = search_idx.get_possible_values(repo_id="mandelbaum", field_names=("outcome",))
        assert values == {"outcome": {"values": ["SUCCESS", "FAIL"]}}
        request = DummyElasticRequests.get_request()
        assert request.get_json_body() == {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": "yadayada"}},
                        {"term": {"repo_id": "mandelbaum"}},
                    ]
                }
            },
            "aggs": {"outcome": {"terms": {"field": "outcome"}}},
            "size": 0,
        }

    def test_get_possible_values_for_fields_branch(self, search_idx: RunInfoSearchIndex) -> None:
        DummyElasticRequests.add_aggregation_response(
            index="buildsense", results=(("branch", ["jerry", "jambalaya", "ovaltine"]),)
        )
        values = search_idx.get_possible_values(repo_id="mandelbaum", field_names=("branch",))
        assert values == {"branch": {"values": ["jerry", "jambalaya", "ovaltine"]}}
        request = DummyElasticRequests.get_request()
        assert request.get_json_body() == {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": "yadayada"}},
                        {"term": {"repo_id": "mandelbaum"}},
                    ]
                }
            },
            "aggs": {"branch": {"terms": {"field": "branch.keyword"}}},
            "size": 0,
        }

    def test_get_possible_values_for_fields_goals(self, search_idx: RunInfoSearchIndex) -> None:
        DummyElasticRequests.add_aggregation_response(
            index="buildsense", results=(("goals", ["minutiae", "yoyoyma", "hennigans"]),)
        )
        values = search_idx.get_possible_values(repo_id="mandelbaum", field_names=("goals",))
        assert values == {"goals": {"values": ["minutiae", "yoyoyma", "hennigans"]}}
        request = DummyElasticRequests.get_request()
        assert request.get_json_body() == {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": "yadayada"}},
                        {"term": {"repo_id": "mandelbaum"}},
                        {"term": {"server_info.stats_version": "3"}},
                    ]
                }
            },
            "aggs": {"goals": {"terms": {"field": "computed_goals"}}},
            "size": 0,
        }

    def test_get_possible_values_for_fields_invalid_field(self, search_idx: RunInfoSearchIndex) -> None:
        with pytest.raises(ToolchainAssertion, match="Not allowed to aggregate on.*customer_id"):
            search_idx.get_possible_values(repo_id="mandelbaum", field_names=("customer_id",))
        DummyElasticRequests.assert_no_requests()

    def test_with_offset(self, search_idx: RunInfoSearchIndex) -> None:
        user = ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")
        customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        repo = Repo.create("kramer", customer=customer, name="Jerry Seinfeld is a funny guy")
        run_infos = self._get_run_infos(user, repo)
        DummyElasticRequests.add_search_response(run_infos[:3], override_total=56)
        DummyElasticRequests.add_search_response(run_infos[4:], override_total=88)
        earliest = datetime.datetime(2019, 6, 17, 3, 1, 48, tzinfo=datetime.timezone.utc)
        latest = datetime.datetime(2019, 8, 27, 10, 33, 21, tzinfo=datetime.timezone.utc)
        fields: FieldsMap = {"outcome": "ABORTED", "cmd_line": "ovaltine"}
        results = search_idx.search_all_matching(
            repo_id="uncle-leo", field_map=fields, earliest=earliest, latest=latest, page_size=12, offset=51
        )
        assert len(results.items) == 3
        assert results.total_count == 56
        expected = self._get_base_query(page_size=12, offset=51)
        expected["query"]["bool"]["must"].extend(
            [
                {"term": {"repo_id": "uncle-leo"}},
                {"range": {"timestamp": {"format": "epoch_second", "gte": 1560740508, "lte": 1566902001}}},
                {"match": {"cmd_line": "ovaltine"}},
                {"term": {"outcome": "ABORTED"}},
            ]
        )
        assert DummyElasticRequests.get_request().get_json_body() == expected

    def test_search_by_pull_request(self, search_idx: RunInfoSearchIndex) -> None:
        user = ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")
        customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        repo = Repo.create("kramer", customer=customer, name="Jerry Seinfeld is a funny guy")
        run_infos = self._get_run_infos(user, repo)
        DummyElasticRequests.add_search_response(run_infos[:3], override_total=56)
        DummyElasticRequests.add_search_response(run_infos[4:], override_total=88)
        earliest = datetime.datetime(2019, 6, 17, 3, 1, 48, tzinfo=datetime.timezone.utc)
        latest = datetime.datetime(2019, 8, 27, 10, 33, 21, tzinfo=datetime.timezone.utc)
        fields: FieldsMap = {"pr": 45722, "goals": ["moops"]}
        results = search_idx.search_all_matching(
            repo_id="uncle-leo",
            field_map=fields,
            earliest=earliest,
            latest=latest,
            page_size=9,
        )
        assert len(results.items) == 3
        assert results.total_count == 56
        expected = self._get_base_query(page_size=9)
        expected["query"]["bool"]["must"].extend(
            [
                {"term": {"repo_id": "uncle-leo"}},
                {"range": {"timestamp": {"format": "epoch_second", "gte": 1560740508, "lte": 1566902001}}},
                {"match_phrase": {"computed_goals": "moops"}},
                {"term": {"ci_info.pull_request": 45722}},
            ]
        )
        assert DummyElasticRequests.get_request().get_json_body() == expected

    def test_get_possible_values_for_fields_pull_request(self, search_idx: RunInfoSearchIndex) -> None:
        DummyElasticRequests.add_aggregation_response(
            index="buildsense", results=(("pr", [22222, 111, 77777, 88888888888]),)
        )
        values = search_idx.get_possible_values(repo_id="mandelbaum", field_names=("pr",))
        assert values == {"pr": {"values": ["22222", "111", "77777", "88888888888"]}}
        search_request = DummyElasticRequests.get_request().get_json_body()
        from_time = search_request["query"]["bool"]["must"][-1]["range"]["timestamp"].pop("gte")
        assert (utcnow() - datetime.timedelta(days=30)).timestamp() == pytest.approx(from_time)
        assert search_request == {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": "yadayada"}},
                        {"term": {"repo_id": "mandelbaum"}},
                        {"range": {"timestamp": {"format": "epoch_second"}}},
                    ]
                }
            },
            "aggs": {"pr": {"terms": {"field": "ci_info.pull_request"}}},
            "size": 0,
        }

    def test_get_title_completion_values(self, search_idx: RunInfoSearchIndex) -> None:
        DummyElasticRequests.add_response("GET", "/buildsense/_search", json_body=load_fixture("es_suggest_response_1"))
        values = search_idx.get_title_completion_values(repo_id="mandelbaum", title_phrase="pr")
        assert values == [
            "Add PR title to PullRequestInfo (#8741)",
            "Add test for buildsense API bug",
            "Add test for buildsense API bug (#8752)",
        ]
        search_request = DummyElasticRequests.get_request().get_json_body()
        assert search_request == {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": "yadayada"}},
                        {"term": {"repo_id": "mandelbaum"}},
                    ]
                }
            },
            "size": 0,
            "_source": "title",
            "suggest": {
                "title_suggest": {"text": "pr", "completion": {"field": "title.completion", "skip_duplicates": True}}
            },
        }

    def test_search_by_title(self, search_idx: RunInfoSearchIndex) -> None:
        user = ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")
        customer = Customer.create(slug="jerry", name="Jerry Seinfeld Inc")
        repo = Repo.create("kramer", customer=customer, name="Jerry Seinfeld is a funny guy")
        run_infos = self._get_run_infos(user, repo)
        DummyElasticRequests.add_search_response(run_infos[:3], override_total=56)
        earliest = datetime.datetime(2019, 6, 17, 3, 1, 48, tzinfo=datetime.timezone.utc)
        latest = datetime.datetime(2019, 8, 27, 10, 33, 21, tzinfo=datetime.timezone.utc)
        fields: FieldsMap = {"title": "no soup for you", "branch": "festivus"}
        results = search_idx.search_all_matching(
            repo_id="uncle-leo",
            field_map=fields,
            earliest=earliest,
            latest=latest,
            page_size=9,
        )
        assert len(results.items) == 3
        assert results.total_count == 56
        expected = self._get_base_query(page_size=9)
        expected["query"]["bool"]["must"].extend(
            [
                {"term": {"repo_id": "uncle-leo"}},
                {"range": {"timestamp": {"format": "epoch_second", "gte": 1560740508, "lte": 1566902001}}},
                {"match": {"branch": "festivus"}},
                {"match": {"title": "no soup for you"}},
            ]
        )
        assert DummyElasticRequests.get_request().get_json_body() == expected

    def test_get_possible_values_multiple_fields_outcome_branch_goal(self, search_idx: RunInfoSearchIndex) -> None:
        DummyElasticRequests.add_aggregation_response(
            index="buildsense",
            results=(
                ("goals", ["minutiae", "yoyoyma", "hennigans"]),
                ("branch", ["jerry", "jambalaya", "ovaltine"]),
                ("outcome", ["SUCCESS", "FAIL"]),
            ),
        )
        values = search_idx.get_possible_values(repo_id="mandelbaum", field_names=("outcome", "branch", "goals"))
        assert values == {
            "outcome": {"values": ["SUCCESS", "FAIL"]},
            "branch": {"values": ["jerry", "jambalaya", "ovaltine"]},
            "goals": {"values": ["minutiae", "yoyoyma", "hennigans"]},
        }
        request = DummyElasticRequests.get_request()
        assert request.get_json_body() == {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": "yadayada"}},
                        {"term": {"repo_id": "mandelbaum"}},
                        {"term": {"server_info.stats_version": "3"}},
                    ]
                }
            },
            "aggs": {
                "outcome": {"terms": {"field": "outcome"}},
                "branch": {"terms": {"field": "branch.keyword"}},
                "goals": {"terms": {"field": "computed_goals"}},
            },
            "size": 0,
        }

    def test_search_timeout(self, search_idx: RunInfoSearchIndex) -> None:
        DummyElasticRequests.add_search_network_error(ConnectionError, "They are running out of shrimp")
        with pytest.raises(SearchTransientError, match=r"ConnectionError.They are running out of shrimp") as excinfo:
            search_idx.search_all_matching(repo_id="uncle-leo", field_map={"goals": ["moops"]}, page_size=16)
        assert excinfo.value.call_name == "search"

    def test_search_http_to_many_requests(self, search_idx: RunInfoSearchIndex) -> None:
        DummyElasticRequests.add_search_http_error_response(http_error_code=429, error_msg="Too Many Request")
        with pytest.raises(SearchTransientError, match=r"TransportError.*Too Many Request") as excinfo:
            search_idx.search_all_matching(repo_id="uncle-leo", field_map={"goals": ["moops"]}, page_size=16)
        assert excinfo.value.call_name == "search"

    def test_search_http_error(self, search_idx: RunInfoSearchIndex) -> None:
        """Make sure we don't intercept/convert non-trainsient errors but rather let them buble up."""
        DummyElasticRequests.add_search_http_error_response(http_error_code=401, error_msg="No soup for you")
        with pytest.raises(TransportError, match=r"AuthenticationException.*No soup for you"):
            search_idx.search_all_matching(repo_id="uncle-leo", field_map={"goals": ["moops"]}, page_size=16)

    def test_get_for_run_id_timeout(self, search_idx: RunInfoSearchIndex) -> None:
        DummyElasticRequests.add_search_network_error(ConnectionError, "They are running out of shrimp")
        with pytest.raises(SearchTransientError, match=r"ConnectionError.They are running out of shrimp") as excinfo:
            search_idx.get_for_run_id(repo_id="puffy-shirt", run_id="cartwright")
        assert excinfo.value.call_name == "get_for_run_id"

    def test_repo_has_builds_true(self, search_idx: RunInfoSearchIndex) -> None:
        DummyElasticRequests.add_has_documents_response(index="buildsense", docs_count=92)
        assert search_idx.repo_has_builds(repo_id="pennypacker") is True
        assert len(DummyElasticRequests.get_requests()) == 1
        search_request = DummyElasticRequests.get_requests()[0].get_json_body()
        assert search_request == {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": "yadayada"}},
                        {"term": {"repo_id": "pennypacker"}},
                    ]
                }
            },
            "size": 0,
        }

    def test_repo_has_builds_false(self, search_idx: RunInfoSearchIndex) -> None:
        DummyElasticRequests.add_has_documents_response(index="buildsense", docs_count=0)
        assert search_idx.repo_has_builds(repo_id="pennypacker") is False
        assert len(DummyElasticRequests.get_requests()) == 1
        search_request = DummyElasticRequests.get_requests()[0].get_json_body()
        assert search_request == {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"server_info.environment": "test"}},
                        {"term": {"customer_id": "yadayada"}},
                        {"term": {"repo_id": "pennypacker"}},
                    ]
                }
            },
            "size": 0,
        }
