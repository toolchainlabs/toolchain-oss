# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

import pytest

from toolchain.base.datetime_tools import utcnow
from toolchain.pants_demos.depgraph.models import DemoRepo, GenerateDepgraphForRepo


@pytest.mark.django_db()
class TestDemoRepoModel:
    def test_create_new(self) -> None:
        assert DemoRepo.objects.count() == 0
        assert GenerateDepgraphForRepo.objects.count() == 0
        now = utcnow()
        dr = DemoRepo.create(account="bob", repo="sacamano")
        assert DemoRepo.objects.count() == 1
        assert GenerateDepgraphForRepo.objects.count() == 1
        loaded_dr = DemoRepo.objects.first()
        assert loaded_dr == dr
        assert loaded_dr.id == GenerateDepgraphForRepo.objects.first().demo_repo_id
        assert loaded_dr.created_at.timestamp() == pytest.approx(now.timestamp())
        assert loaded_dr.repo_account == "bob"
        assert loaded_dr.repo_name == "sacamano"
        assert loaded_dr.processing_state == DemoRepo.State.NOT_PROCESSED
        assert loaded_dr.is_successful is False
        assert loaded_dr.is_failed is False
        assert loaded_dr.processing_state.display_name == "Not processed"
        assert loaded_dr.last_processed is None
        assert loaded_dr.branch_name == ""
        assert loaded_dr.commit_sha == ""
        assert loaded_dr.num_of_targets is None
        assert loaded_dr.result_location == ""
        assert loaded_dr.repo_full_name == "bob/sacamano"

    def test_create_new_exists(self) -> None:
        original_dr = DemoRepo.objects.create(
            repo_account="bob",
            repo_name="sacamano",
            _processing_state=DemoRepo.State.SUCCESS.value,
            branch_name="comso",
            commit_sha="kramer",
            result_location="it’s not a lie if you believe it",
        )

        assert DemoRepo.objects.count() == 1
        assert GenerateDepgraphForRepo.objects.count() == 0
        dr = DemoRepo.create(account="bob", repo="sacamano")
        loaded_dr = DemoRepo.objects.first()
        assert loaded_dr == dr == original_dr
        assert loaded_dr.repo_account == "bob"
        assert loaded_dr.repo_name == "sacamano"
        assert loaded_dr.last_processed is None
        assert loaded_dr.processing_state == DemoRepo.State.SUCCESS
        assert loaded_dr.is_successful is True
        assert loaded_dr.is_failed is False
        assert loaded_dr.processing_state.display_name == "Success"
        assert loaded_dr.branch_name == "comso"
        assert loaded_dr.commit_sha == "kramer"
        assert loaded_dr.num_of_targets is None
        assert loaded_dr.result_location == "it’s not a lie if you believe it"
        assert loaded_dr.repo_full_name == "bob/sacamano"

    def test_start_processing(self) -> None:
        dr = DemoRepo.create(account="bob", repo="sacamano")
        now = utcnow()
        dr.start_processing(s3_url="it’s not a lie if you believe it")
        assert DemoRepo.objects.count() == 1
        loaded_dr = DemoRepo.objects.first()
        assert loaded_dr == dr
        assert loaded_dr.processing_state == DemoRepo.State.PROCESSING
        assert loaded_dr.processing_state.display_name == "Processing"
        assert loaded_dr.is_successful is False
        assert loaded_dr.is_failed is False
        assert loaded_dr.branch_name == ""
        assert loaded_dr.commit_sha == ""
        assert loaded_dr.num_of_targets is None
        assert loaded_dr.result_location == "it’s not a lie if you believe it"
        assert loaded_dr.repo_full_name == "bob/sacamano"
        assert loaded_dr.last_processed.timestamp() == pytest.approx(now.timestamp())

    def test_set_result_success(self) -> None:
        dr = DemoRepo.create(account="bob", repo="sacamano")
        dr.set_success_result(
            branch="moles", commit_sha="puddy", num_of_targets=83, processing_time=datetime.timedelta(minutes=20)
        )
        assert DemoRepo.objects.count() == 1
        loaded_dr = DemoRepo.objects.first()
        assert loaded_dr == dr
        assert loaded_dr.processing_state == DemoRepo.State.SUCCESS
        assert loaded_dr.processing_state.display_name == "Success"
        assert loaded_dr.is_successful is True
        assert loaded_dr.is_failed is False
        assert loaded_dr.branch_name == "moles"
        assert loaded_dr.commit_sha == "puddy"
        assert loaded_dr.num_of_targets == 83
        assert loaded_dr.processing_time == datetime.timedelta(minutes=20)
        assert loaded_dr.result_location == ""
        assert loaded_dr.repo_full_name == "bob/sacamano"
        assert loaded_dr.last_processed is None

    def test_set_result_fail(self) -> None:
        dr = DemoRepo.create(account="bob", repo="sacamano")
        dr.set_failure_result(reason="feats of strength", processing_time=None)
        assert DemoRepo.objects.count() == 1
        loaded_dr = DemoRepo.objects.first()
        assert loaded_dr == dr
        assert loaded_dr.processing_state == DemoRepo.State.FAILURE
        assert loaded_dr.processing_state.display_name == "Failure"
        assert loaded_dr.is_successful is False
        assert loaded_dr.branch_name == ""
        assert loaded_dr.commit_sha == ""
        assert loaded_dr.num_of_targets is None
        assert loaded_dr.result_location == ""
        assert loaded_dr.processing_time is None
        assert loaded_dr.repo_full_name == "bob/sacamano"
        assert loaded_dr.fail_reason == "feats of strength"
        assert loaded_dr.last_processed is None
