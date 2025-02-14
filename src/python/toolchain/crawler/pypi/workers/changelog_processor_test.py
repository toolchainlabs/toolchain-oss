# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime

import pytest
from requests.exceptions import SSLError

from toolchain.crawler.base.models import FetchURL
from toolchain.crawler.pypi.models import ProcessChangelog, ProcessDistribution
from toolchain.crawler.pypi.test_helpers.helpers import (
    add_project_response,
    add_projects_responses,
    load_fixture,
    mock_changelog_since_serial,
    mock_changelog_since_serial_error,
)
from toolchain.crawler.pypi.workers.changelog_processor import AddedDists, ChangelogProcessor
from toolchain.crawler.pypi.xmlrpc_api import ChangeLogEntry
from toolchain.packagerepo.pypi.models import Distribution, Project, Release
from toolchain.workflow.error import AdvisoryWorkException


def load_added_dists(fixture_name: str) -> AddedDists:
    fixture = load_fixture(fixture_name)
    cl_entries = [ChangeLogEntry(**entry_json) for entry_json in fixture["entries"]]
    dists = {dist["filename"]: dist for dist in fixture["distributions"]}
    return [(entry, dists[entry.filename]) for entry in cl_entries]


@pytest.mark.django_db()
class TestChangelogProcessor:
    def test_process_added(self) -> None:
        assert Project.objects.count() == 0
        assert Release.objects.count() == 0
        assert Distribution.objects.count() == 0
        payload = ProcessChangelog.create(serial_from=100, serial_to=300)
        processor = ChangelogProcessor()
        added_dists_tuples = load_added_dists("change_log_entries_1")
        dists_to_urls = {entry.filename: dist["url"] for entry, dist in added_dists_tuples}
        assert len(added_dists_tuples) == 10
        added_dists = processor._process_added(payload, added_dists_tuples)
        assert len(added_dists) == 10
        work_unit = payload.work_unit
        work_unit.refresh_from_db()
        assert work_unit.num_unsatisfied_requirements == 10
        process_dists_qs = work_unit.requirements.all()
        assert process_dists_qs.count() == 10
        assert {ProcessDistribution} == {type(wu.payload) for wu in process_dists_qs}
        for wu in process_dists_qs:
            assert isinstance(wu.payload, ProcessDistribution)
            assert wu.num_unsatisfied_requirements == 1
            assert wu.requirements.count() == 1
            fetch_url = wu.requirements.first().payload
            assert isinstance(fetch_url, FetchURL)
            dist = wu.payload.distribution
            assert fetch_url.url == dist.url
            # Not equal because we add a sha256 to the end of the urls we save to the db.
            assert fetch_url.url.startswith(dists_to_urls[dist.filename])

        assert {1} == {wu.num_unsatisfied_requirements for wu in process_dists_qs}
        assert Project.objects.count() == 5
        assert Release.objects.count() == 5
        assert Distribution.objects.count() == 10
        # Sample created pypi package repo data
        proj = Project.get_or_none(name="kintyre-splunk-conf")
        assert proj is not None
        assert proj.releases.count() == 1
        release = proj.releases.first()
        assert release.version == "0.8b1"
        assert release.distributions.count() == 2
        sdist = release.distributions.get(dist_type="SDIST")
        wheel = release.distributions.get(dist_type="WHEEL")
        assert sdist.filename == "kintyre-splunk-conf-0.8b1.tar.gz"
        assert wheel.filename == "kintyre_splunk_conf-0.8b1-py2.py3-none-any.whl"

    def _assert_entry(self, entry: ChangeLogEntry, *, project: str, version: str, filename: str, serial: int) -> None:
        assert entry.project == project
        assert entry.version == version
        assert entry.filename == filename
        assert entry.serial == serial

    @mock_changelog_since_serial("changelog_since_serial_1")
    def test_do_work_ignore_items(self, responses) -> None:
        add_projects_responses(responses, 7_200_000, "pythonslm", "hippounit")
        payload = ProcessChangelog.create(serial_from=3140, serial_to=7_198_869)

        processor = ChangelogProcessor()
        assert processor.do_work(payload) is False
        added_dist_dicts = processor._added_dist_dicts
        assert len(added_dist_dicts) == 3
        assert len(processor._removed_files) == 0
        assert len(responses.calls) == 3

        self._assert_entry(
            added_dist_dicts[0][0],
            project="hippounit",
            version="1.3.4",
            filename="hippounit-1.3.4-py2-none-any.whl",
            serial=7198861,
        )
        self._assert_entry(
            added_dist_dicts[1][0],
            project="hippounit",
            version="1.3.4",
            filename="hippounit-1.3.4.tar.gz",
            serial=7198862,
        )
        self._assert_entry(
            added_dist_dicts[2][0],
            project="pythonslm",
            version="0.1",
            filename="PythonSLM-0.1-py3.7-linux-x86_64.egg",
            serial=7198867,
        )
        assert added_dist_dicts[2][1] == {
            "comment_text": "",
            "digests": {
                "md5": "d6743b83631378f765001a2ccf951066",
                "sha256": "23d9b81c439a1ca9924246b0b9b6def8d19ad7208bbeebde3c7927b9f77dfef4",
            },
            "downloads": -1,
            "filename": "PythonSLM-0.1-py3.7-linux-x86_64.egg",
            "has_sig": False,
            "md5_digest": "d6743b83631378f765001a2ccf951066",
            "packagetype": "bdist_egg",
            "python_version": "3.7",
            "requires_python": ">=3.5",
            "size": 1688661,
            "upload_time": "2020-05-08T17:48:30",
            "upload_time_iso_8601": "2020-05-08T17:48:30.164603Z",
            "url": "https://files.pythonhosted.org/packages/d3/95/c30c7abf8a3950ab4b7e65fc9f874cc75e2a5e0d24cf59e9aeba7eaecd97/PythonSLM-0.1-py3.7-linux-x86_64.egg",
            "yanked": False,
            "dist_type": "BDIST",
        }

    @mock_changelog_since_serial("changelog_since_serial_2")
    def test_do_work(self, responses) -> None:
        add_projects_responses(responses, 7_400_000, "todo-placeholder", "opencensus-ext-zenoss")
        payload = ProcessChangelog.create(serial_from=3140, serial_to=7_399_999)
        processor = ChangelogProcessor()
        assert processor.do_work(payload) is False
        added_dist_dicts = processor._added_dist_dicts
        assert not processor._stale_projects
        assert processor._retry_interval is None
        assert len(added_dist_dicts) == 3
        assert len(processor._removed_files) == 2

        assert len(responses.calls) == 3
        self._assert_entry(
            added_dist_dicts[1][0],
            project="todo-placeholder",
            version="1.0.1",
            filename="todo-placeholder-1.0.1.tar.gz",
            serial=7200236,
        )
        assert processor._removed_files == [
            ("MetaStalk-2.2.0.linux-x86_64.tar.gz", 7200237),
            ("MetaStalk-2.2.0-py3-none-any.whl", 7200238),
        ]

    @mock_changelog_since_serial("changelog_since_serial_2")
    def test_do_work_stale_projects(self, responses) -> None:
        add_projects_responses(responses, 7_400_000, "todo-placeholder")
        add_projects_responses(responses, 7_100_000, "opencensus-ext-zenoss")  # stale
        responses.add("PURGE", "https://pypi.org/pypi/opencensus-ext-zenoss/json")
        payload = ProcessChangelog.create(serial_from=7_200_000, serial_to=7_399_999)
        processor = ChangelogProcessor()
        assert processor.do_work(payload) is False
        assert processor._retry_interval == datetime.timedelta(minutes=5)
        assert len(responses.calls) == 4
        assert responses.calls[-1].request.method == "PURGE"
        assert processor._stale_projects == ["opencensus-ext-zenoss"]
        assert not processor._removed_files
        assert len(processor._added_dist_dicts) == 2

    @mock_changelog_since_serial("changelog_since_serial_1")
    def test_do_work_missing_serial_header(self, responses) -> None:
        add_projects_responses(responses, 7_200_000, "hippounit")
        add_projects_responses(responses, 0, "pythonslm")
        responses.add("PURGE", "https://pypi.org/pypi/pythonslm/json")
        payload = ProcessChangelog.create(serial_from=7_200_000, serial_to=7_399_999)
        processor = ChangelogProcessor()
        assert processor.do_work(payload) is False
        assert processor._retry_interval == datetime.timedelta(minutes=5)
        assert len(responses.calls) == 4
        assert responses.calls[-1].request.method == "PURGE"
        assert processor._stale_projects == ["pythonslm"]
        assert not processor._removed_files
        assert len(processor._added_dist_dicts) == 2

    @mock_changelog_since_serial("changelog_since_serial_2")
    def test_do_work_get_project_data_failure(self, responses) -> None:
        responses.add(responses.GET, url="https://pypi.org/pypi/todo-placeholder/json", body=SSLError())
        payload = ProcessChangelog.create(serial_from=3140, serial_to=7_399_999)
        processor = ChangelogProcessor()
        assert processor.do_work(payload) is False
        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == "https://pypi.org/pypi/todo-placeholder/json"
        assert processor._retry_interval == datetime.timedelta(minutes=10)

    @mock_changelog_since_serial_error("Service Unavailable")
    def test_do_work_get_changed_packages_failure(self) -> None:
        payload = ProcessChangelog.create(serial_from=7_200_000, serial_to=7_399_999)
        processor = ChangelogProcessor()
        assert processor.do_work(payload) is False
        assert processor._retry_interval == datetime.timedelta(minutes=15)

    @mock_changelog_since_serial("changelog_since_serial_2")
    def test_unknown_package_type(self, responses) -> None:
        headers = {"X-PYPI-LAST-SERIAL": str(7_400_000)}
        add_project_response(responses, headers=headers, project="todo-placeholder")
        add_project_response(
            responses, headers=headers, project="opencensus-ext-zenoss", fixture="opencensus-ext-zenoss-invalid"
        )
        payload = ProcessChangelog.create(serial_from=3140, serial_to=7_399_999)
        processor = ChangelogProcessor()
        with pytest.raises(AdvisoryWorkException, match="Unsupported packagetype: jambalaya"):
            processor.do_work(payload)

    @mock_changelog_since_serial("changelog_with_long_project_name")
    def test_long_project_name(self, responses) -> None:
        headers = {"X-PYPI-LAST-SERIAL": str(7_400_000)}
        add_project_response(
            responses,
            headers=headers,
            project="no-soup-for-you-come-back-one-year-program-to-get-any-string-as-user-input-and-output-code-for-the-string-reverse-the-string-and-code-using-alphabet-position-program-to-get-any-string-as-user-input-and-output-code-for-the-string-reverse-the-string-and-code-using-alphabet-position",
            fixture="todo-placeholder",
        )
        payload = ProcessChangelog.create(serial_from=200_200, serial_to=11_210_350)
        processor = ChangelogProcessor()
        assert processor.do_work(payload) is False
        assert len(processor._added_dist_dicts) == 2
        processor.on_reschedule(payload)
        assert Project.objects.count() == 0
        assert Release.objects.count() == 0
        assert Distribution.objects.count() == 0
