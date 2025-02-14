# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json

import pytest
from freezegun import freeze_time
from jose import jwt
from jose.constants import ALGORITHMS
from moto import mock_s3

from toolchain.aws.s3 import S3
from toolchain.aws.test_utils.s3_utils import assert_bucket_empty, create_s3_bucket
from toolchain.base.datetime_tools import utcnow
from toolchain.bitbucket_integration.common.events import WebhookEvent
from toolchain.bitbucket_integration.hook_handlers import HookHandleFailure, run_handler
from toolchain.bitbucket_integration.models import BitbucketAppInstall
from toolchain.bitbucket_integration.test_utils.fixtures_loader import load_fixture
from toolchain.django.site.models import Customer, Repo


def load_webhook_fixture(name: str, shared_secret: str | None = None, update_expiration: bool = False) -> WebhookEvent:
    fixture = load_fixture(name)
    payload = json.dumps(fixture["payload"]).encode()
    headers = fixture["headers"]
    if shared_secret:  # Replace jwt signature
        claims = jwt.get_unverified_claims(headers["Authorization"].partition(" ")[2])
        if update_expiration:
            claims["exp"] = int((utcnow() + datetime.timedelta(hours=1)).timestamp())
        updated_token = jwt.encode(claims, key=shared_secret, algorithm=ALGORITHMS.HS256)
        headers["Authorization"] = f"JWT {updated_token}"
    return WebhookEvent.create(headers=headers, body=payload)


@pytest.mark.django_db()
class TestHookHandlers:
    _BUCKET = "fake-scm-integration-bucket"

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_s3():
            create_s3_bucket(self._BUCKET)
            yield

    @pytest.fixture()
    def customer(self) -> Customer:
        return Customer.create(slug="jerry", name="Jerry Seinfeld Inc", scm=Customer.Scm.BITBUCKET)

    @pytest.fixture()
    def repo(self, customer: Customer) -> Repo:
        return Repo.create(slug="minimal-pants", customer=customer, name="Maybe the dingo ate your baby")

    @pytest.fixture()
    def app_install(self, customer: Customer) -> BitbucketAppInstall:
        return BitbucketAppInstall.objects.create(
            customer_id=customer.id,
            account_name="No-Bagels",
            account_id="{acf54878-51be-473e-bf0b-0fbb12e011ad}",
            client_key="ari:cloud:bitbucket::app/{acf54878-51be-473e-bf0b-0fbb12e011ad}/toolchain-dev",
            shared_secret="hestoppedshort",
        )

    @freeze_time(datetime.datetime(2021, 7, 28, 14, 50, tzinfo=datetime.timezone.utc))
    def test_pull_request_created(self, repo: Repo, app_install: BitbucketAppInstall) -> None:
        webhook_event = load_webhook_fixture("pullrequest_created", shared_secret=app_install.shared_secret)
        assert run_handler(webhook_event) is True
        s3 = S3()
        key = f"moles/freckles/pull_request/{repo.customer_id}/{repo.id}/9.json"
        assert s3.exists(bucket=self._BUCKET, key=key) is True
        json_data = json.loads(s3.get_content(bucket=self._BUCKET, key=key))
        assert json_data["data"]["pullrequest"]["title"] == "Add & run linters"

    @freeze_time(datetime.datetime(2021, 7, 28, 14, 50, tzinfo=datetime.timezone.utc))
    def test_pull_request_created_no_repo(self, app_install: BitbucketAppInstall) -> None:
        webhook_event = load_webhook_fixture("pullrequest_created", shared_secret=app_install.shared_secret)
        with pytest.raises(HookHandleFailure, match="no active repo for festivus-miracle/minimal-pants") as excinfo:
            run_handler(webhook_event)
        assert excinfo.value.critical is False

    def test_no_handler(self, app_install: BitbucketAppInstall) -> None:
        fixture = load_fixture("repo_commit_status_created")
        fixture["headers"]["X-Event-Key"] = "the dingo ate your baby"
        webhook_event = WebhookEvent.create(headers=fixture["headers"], body=json.dumps(fixture["payload"]).encode())
        with pytest.raises(
            HookHandleFailure, match="no handler for webhook_event.event_type='the dingo ate your baby'"
        ) as excinfo:
            assert run_handler(webhook_event) is False
        assert excinfo.value.critical is False

    def test_ignore(self, app_install: BitbucketAppInstall) -> None:
        webhook_event = load_webhook_fixture("repo_commit_status_created", shared_secret=app_install.shared_secret)
        assert run_handler(webhook_event) is False

    def test_pull_request_created_token_expiration(self, app_install: BitbucketAppInstall) -> None:
        webhook_event = load_webhook_fixture("pullrequest_created", shared_secret=app_install.shared_secret)
        with pytest.raises(HookHandleFailure, match="Bad JWT: Signature has expired. for account=No-Bagels") as excinfo:
            run_handler(webhook_event)
        assert excinfo.value.critical is True

    def test_pull_request_created_app_uninstalled(self, customer: Customer, app_install: BitbucketAppInstall) -> None:
        webhook_event = load_webhook_fixture("pullrequest_created", shared_secret=app_install.shared_secret)
        app_install.set_uninstall(app_install.account_name, customer.id)
        with pytest.raises(HookHandleFailure, match="No app install info for workspace") as excinfo:
            run_handler(webhook_event)
        assert excinfo.value.critical is False

    def test_pull_request_created_token_invalid_signature(self, app_install: BitbucketAppInstall) -> None:
        webhook_event = load_webhook_fixture("pullrequest_created")
        with pytest.raises(
            HookHandleFailure, match="Bad JWT: Signature verification failed. for account=No-Bagels"
        ) as excinfo:
            run_handler(webhook_event)
        assert excinfo.value.critical is True

    @freeze_time(datetime.datetime(2021, 7, 28, 14, 50, tzinfo=datetime.timezone.utc))
    def test_pull_request_created_invalid_audience(self, app_install: BitbucketAppInstall) -> None:
        app_install.client_key = "no-bagels"
        app_install.save()
        webhook_event = load_webhook_fixture("pullrequest_created", shared_secret=app_install.shared_secret)
        with pytest.raises(HookHandleFailure, match="Bad JWT: Invalid audience for account=No-Bagels") as excinfo:
            run_handler(webhook_event)
        assert excinfo.value.critical is True

    @freeze_time(datetime.datetime(2021, 7, 28, 14, 50, tzinfo=datetime.timezone.utc))
    def test_repo_push_branch(self, repo: Repo, app_install: BitbucketAppInstall) -> None:
        webhook_event = load_webhook_fixture("repo_push_pr_merge", shared_secret=app_install.shared_secret)
        assert run_handler(webhook_event) is True
        s3 = S3()
        key = f"moles/freckles/push/{repo.customer_id}/{repo.id}/branch/main/d98f3c1d2ad48d6f7ed51281eb28ad3b233878c4.json"
        assert s3.exists(bucket=self._BUCKET, key=key) is True
        json_data = json.loads(s3.get_content(bucket=self._BUCKET, key=key))
        assert (
            json_data["data"]["push"]["changes"][0]["new"]["target"]["message"]
            == "Merged in upgrades (pull request #9)\n\nAdd & run linters"
        )

    @freeze_time(datetime.datetime(2021, 8, 12, 0, 52, 11, tzinfo=datetime.timezone.utc))
    def test_repo_push_delete_branch(self, repo: Repo, app_install: BitbucketAppInstall) -> None:
        webhook_event = load_webhook_fixture("repo_push_delete_branch", shared_secret=app_install.shared_secret)
        assert run_handler(webhook_event) is True
        assert_bucket_empty(S3(), self._BUCKET)
