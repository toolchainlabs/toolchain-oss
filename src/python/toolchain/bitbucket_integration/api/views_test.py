# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json

import pytest
from jose import jwt
from moto import mock_s3

from toolchain.aws.s3 import S3
from toolchain.aws.test_utils.s3_utils import create_s3_bucket
from toolchain.base.datetime_tools import utcnow
from toolchain.bitbucket_integration.hook_handlers_test import load_webhook_fixture
from toolchain.bitbucket_integration.models import BitbucketAppInstall
from toolchain.bitbucket_integration.test_utils.fixtures_loader import load_fixture, load_fixture_payload
from toolchain.django.site.models import Customer, Repo


@pytest.mark.django_db()
class TestAppInstallView:
    @pytest.fixture()
    def bitbucket_customer(self) -> Customer:
        return Customer.create(slug="tinsel", name="Festivus For the rest of us", scm=Customer.Scm.BITBUCKET)

    @pytest.fixture()
    def github_customer(self) -> Customer:
        return Customer.create(slug="bagels", name="H&H Bagels")

    @pytest.fixture()
    def jwt_token(self, settings) -> str:
        now_ts = int(utcnow().timestamp())
        assert settings.BITBUCKET_CONFIG.secret == "the bus boy is coming"
        return jwt.encode(
            claims={
                "iss": "ari:cloud:bitbucket::app/{acf54878-51be-473e-bf0b-0fbb12e011ad}/toolchain-dev",
                "iat": now_ts,
                "qsh": "558563f29d5457e68521c3a1aa2caf0d46b7cf9820f1328a184cb75cc2bd656b",
                "aud": "ari:cloud:bitbucket::app/{acf54878-51be-473e-bf0b-0fbb12e011ad}/toolchain-dev",
                "exp": now_ts + 120,
            },
            key="the bus boy is coming",
            algorithm=jwt.ALGORITHMS.HS256,
        )

    @pytest.fixture()
    def installed_app(self, bitbucket_customer: Customer) -> BitbucketAppInstall:
        return BitbucketAppInstall.objects.create(
            customer_id=bitbucket_customer.id,
            account_name="No-Bagels",
            account_id="{acf54878-51be-473e-bf0b-0fbb12e011ad}",
            client_key="ari:cloud:bitbucket::app/{acf54878-51be-473e-bf0b-0fbb12e011ad}/toolchain-dev",
            shared_secret="the bus boy is coming",
        )

    def test_app_install_team(self, bitbucket_customer: Customer, client, jwt_token: str) -> None:
        assert BitbucketAppInstall.objects.count() == 0
        response = client.post(
            "/api/v1/bitbucket/app/install/",
            content_type="application/json",
            data={
                "account_name": "Tinsel",
                "account_id": "{acf54878-51be-473e-bf0b-0fbb12e011ad}",
                "client_key": "ari:cloud:bitbucket::app/{acf54878-51be-473e-bf0b-0fbb12e011ad}/toolchain-dev",
                "shared_secret": "it’s human to be moved by a fragrance",
                "account_type": "team",
                "account_url": "https://moles.jerry.seinfeld/accounts",
                "jwt": jwt_token,
            },
        )
        assert response.status_code == 201
        assert BitbucketAppInstall.objects.count() == 1
        install = BitbucketAppInstall.objects.first()
        assert install.customer_id == bitbucket_customer.id
        assert install.account_name == "Tinsel"
        assert install.account_id == "{acf54878-51be-473e-bf0b-0fbb12e011ad}"
        assert install.client_key == "ari:cloud:bitbucket::app/{acf54878-51be-473e-bf0b-0fbb12e011ad}/toolchain-dev"
        assert install.shared_secret == "it’s human to be moved by a fragrance"

    def _add_user_account_response(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="GET",
            url="https://api.bitbucket.org/2.0/users/%7B2a216c6c-4d18-4ad7-a486-9fddb5119b0a%7D",
            json=load_fixture("user_info_response"),
        )

    def test_app_install_user(self, httpx_mock, client, jwt_token: str) -> None:
        customer = Customer.create(slug="abhisheK", name="Festivus For the rest of us", scm=Customer.Scm.BITBUCKET)
        self._add_user_account_response(httpx_mock)
        assert BitbucketAppInstall.objects.count() == 0
        response = client.post(
            "/api/v1/bitbucket/app/install/",
            content_type="application/json",
            data={
                "account_name": "",
                "account_id": "602fd0fe9f84a90069078512",
                "client_key": "ari:cloud:bitbucket::app/{acf54878-51be-473e-bf0b-0fbb12e011ad}/toolchain-dev",
                "shared_secret": "",
                "account_type": "user",
                "account_url": "https://api.bitbucket.org/2.0/users/%7B2a216c6c-4d18-4ad7-a486-9fddb5119b0a%7D",
                "jwt": jwt_token,
            },
        )
        assert response.status_code == 201
        assert BitbucketAppInstall.objects.count() == 1
        install = BitbucketAppInstall.objects.first()
        assert install.customer_id == customer.id
        assert install.account_name == "AbhisheK"
        assert install.account_id == "602fd0fe9f84a90069078512"
        assert install.client_key == "ari:cloud:bitbucket::app/{acf54878-51be-473e-bf0b-0fbb12e011ad}/toolchain-dev"
        assert install.shared_secret == ""

    def test_app_install_user_no_customer(self, httpx_mock, client, jwt_token: str) -> None:
        self._add_user_account_response(httpx_mock)
        assert BitbucketAppInstall.objects.count() == 0
        response = client.post(
            "/api/v1/bitbucket/app/install/",
            content_type="application/json",
            data={
                "account_name": "",
                "account_id": "602fd0fe9f84a90069078512",
                "client_key": "ari:cloud:bitbucket::app/{acf54878-51be-473e-bf0b-0fbb12e011ad}/toolchain-dev",
                "shared_secret": "",
                "account_type": "user",
                "account_url": "https://api.bitbucket.org/2.0/users/%7B2a216c6c-4d18-4ad7-a486-9fddb5119b0a%7D",
                "jwt": jwt_token,
            },
        )
        assert response.status_code == 404
        assert BitbucketAppInstall.objects.count() == 0

    def test_app_uninstall_team(
        self, bitbucket_customer: Customer, installed_app: BitbucketAppInstall, client, jwt_token: str
    ) -> None:
        assert BitbucketAppInstall.objects.count() == 1
        response = client.patch(
            "/api/v1/bitbucket/app/install/",
            content_type="application/json",
            data={
                "account_name": "Tinsel",
                "account_id": "{acf54878-51be-473e-bf0b-0fbb12e011ad}",
                "client_key": "ari:cloud:bitbucket::app/{acf54878-51be-473e-bf0b-0fbb12e011ad}/toolchain-dev",
                "jwt": jwt_token,
                "account_type": "team",
                "account_url": "https://moles.jerry.seinfeld/accounts",
            },
        )
        assert response.status_code == 201
        assert BitbucketAppInstall.objects.count() == 1
        loaded_app_install = BitbucketAppInstall.objects.first()
        assert loaded_app_install.app_state == BitbucketAppInstall.State.UNINSTALLED
        assert loaded_app_install.account_name == "Tinsel"

    def test_app_install_bad_jwt(self, bitbucket_customer: Customer, client, jwt_token: str) -> None:
        assert BitbucketAppInstall.objects.count() == 0
        response = client.post(
            "/api/v1/bitbucket/app/install/",
            content_type="application/json",
            data={
                "account_name": "Tinsel",
                "account_id": "{acf54878-51be-473e-bf0b-0fbb12e011ad}",
                "client_key": "ari:cloud:bitbucket::app/{acf54878-51be-473e-bf0b-0fbb12e011ad}/toolchain-dev",
                "shared_secret": "it’s human to be moved by a fragrance",
                "account_type": "team",
                "account_url": "https://moles.jerry.seinfeld/accounts",
                "jwt": jwt_token[:-10],
            },
        )
        assert response.status_code == 403
        assert BitbucketAppInstall.objects.count() == 0

    def test_app_uninstall_team_no_op(self, bitbucket_customer: Customer, client, jwt_token: str) -> None:
        assert BitbucketAppInstall.objects.count() == 0
        response = client.patch(
            "/api/v1/bitbucket/app/install/",
            content_type="application/json",
            data={
                "account_name": "Tinsel",
                "account_id": "{acf54878-51be-473e-bf0b-0fbb12e011ad}",
                "client_key": "ari:cloud:bitbucket::app/{acf54878-51be-473e-bf0b-0fbb12e011ad}/toolchain-dev",
                "account_type": "team",
                "account_url": "https://moles.jerry.seinfeld/accounts",
                "jwt": jwt_token,
            },
        )
        assert response.status_code == 200
        assert BitbucketAppInstall.objects.count() == 0

    def test_app_uninstall_team_no_customer(self, client, jwt_token: str) -> None:
        assert BitbucketAppInstall.objects.count() == 0
        response = client.patch(
            "/api/v1/bitbucket/app/install/",
            content_type="application/json",
            data={
                "account_name": "Tinsel",
                "account_id": "{acf54878-51be-473e-bf0b-0fbb12e011ad}",
                "client_key": "ari:cloud:bitbucket::app/{acf54878-51be-473e-bf0b-0fbb12e011ad}/toolchain-dev",
                "account_type": "team",
                "account_url": "https://moles.jerry.seinfeld/accounts",
                "jwt": jwt_token,
            },
        )
        assert response.status_code == 404
        assert BitbucketAppInstall.objects.count() == 0

    def test_app_uninstall_team_github_customer(self, github_customer: Customer, client, jwt_token: str) -> None:
        assert BitbucketAppInstall.objects.count() == 0
        response = client.patch(
            "/api/v1/bitbucket/app/install/",
            content_type="application/json",
            data={
                "account_name": "bagels",
                "account_id": "{acf54878-51be-473e-bf0b-0fbb12e011ad}",
                "client_key": "ari:cloud:bitbucket::app/{acf54878-51be-473e-bf0b-0fbb12e011ad}/toolchain-dev",
                "account_type": "team",
                "account_url": "https://moles.jerry.seinfeld/accounts",
                "jwt": jwt_token,
            },
        )
        assert response.status_code == 400
        assert BitbucketAppInstall.objects.count() == 0

    def test_app_uninstall_bad_jwt(
        self, bitbucket_customer: Customer, installed_app: BitbucketAppInstall, client, jwt_token: str
    ) -> None:
        assert BitbucketAppInstall.objects.count() == 1
        response = client.patch(
            "/api/v1/bitbucket/app/install/",
            content_type="application/json",
            data={
                "account_name": "Tinsel",
                "account_id": "{acf54878-51be-473e-bf0b-0fbb12e011ad}",
                "client_key": "ari:cloud:bitbucket::app/{acf54878-51be-473e-bf0b-0fbb12e011ad}/toolchain-dev",
                "jwt": jwt_token[3:],
                "account_type": "team",
                "account_url": "https://moles.jerry.seinfeld/accounts",
            },
        )
        assert response.status_code == 403
        assert BitbucketAppInstall.objects.count() == 1
        loaded_app_install = BitbucketAppInstall.objects.first()
        assert loaded_app_install.app_state == BitbucketAppInstall.State.INSTALLED
        assert loaded_app_install.account_name == "No-Bagels"


@pytest.mark.django_db()
class TestWebhookView:
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
            shared_secret="bobsacamano",
        )

    def load_webhook_fixture(self, name: str, app_install: BitbucketAppInstall) -> dict:
        webhook_event = load_webhook_fixture(name, app_install.shared_secret, update_expiration=True)
        return webhook_event.to_json_dict()

    def _post_webhook(self, client, payload: dict):
        return client.post("/api/v1/bitbucket/webhook/", content_type="application/json", data=payload)

    def test_pull_request_created(self, repo: Repo, client, app_install: BitbucketAppInstall) -> None:
        payload = self.load_webhook_fixture("pullrequest_created", app_install)
        response = self._post_webhook(client, payload)
        assert response.status_code == 201
        s3 = S3()
        key = f"moles/freckles/pull_request/{repo.customer_id}/{repo.id}/9.json"
        assert s3.exists(bucket=self._BUCKET, key=key) is True
        json_data = json.loads(s3.get_content(bucket=self._BUCKET, key=key))
        assert json_data["data"]["pullrequest"]["title"] == "Add & run linters"

    def test_no_handler(self, client, app_install: BitbucketAppInstall) -> None:
        payload = self.load_webhook_fixture("repo_commit_status_created", app_install)
        payload["event_type"] = "freckles’ ugly cousin"
        response = self._post_webhook(client, payload)
        assert response.status_code == 200


@pytest.mark.django_db()
class TestPullRequestView:
    _BUCKET = "fake-scm-integration-bucket"

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_s3():
            create_s3_bucket(self._BUCKET)
            yield

    def test_get_pr(self, client) -> None:
        fixture = load_fixture_payload("pullrequest_updated")
        S3().upload_json_str(
            bucket=self._BUCKET, key="moles/freckles/pull_request/mail/newman/7.json", json_str=json.dumps(fixture)
        )
        response = client.get("/api/v1/bitbucket/mail/newman/pull_requests/7/")
        assert response.status_code == 200
        assert response.json() == {"pull_request_data": fixture["data"]["pullrequest"]}

    def test_get_non_existent_pr(self, client) -> None:
        response = client.get("/api/v1/bitbucket/mail/newman/pull_requests/7/")
        assert response.status_code == 404
        assert response.content == b'{"detail":"Not found."}'


@pytest.mark.django_db()
class TestPushView:
    _BUCKET = "fake-scm-integration-bucket"

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_s3():
            create_s3_bucket(self._BUCKET)
            yield

    def test_get_tag_push(self, client) -> None:
        fixture = load_fixture_payload("repo_push_create_tag")
        S3().upload_json_str(
            bucket=self._BUCKET,
            key="moles/freckles/push/mail/newman/tag/feats-of-strength/d98f3c1d2ad48d6f7ed51281eb28ad3b233878c4.json",
            json_str=json.dumps(fixture),
        )
        response = client.get(
            "/api/v1/bitbucket/mail/newman/push/tag/feats-of-strength/d98f3c1d2ad48d6f7ed51281eb28ad3b233878c4/"
        )
        assert response.status_code == 200
        assert response.json() == {
            "change": fixture["data"]["push"]["changes"][0],
            "actor": {
                "display_name": "Asher Foa",
                "uuid": "{6ae3c307-ae59-4135-9c72-bdd06eb2010a}",
                "links": {
                    "self": {"href": "https://api.bitbucket.org/2.0/users/%7B6ae3c307-ae59-4135-9c72-bdd06eb2010a%7D"},
                    "html": {"href": "https://bitbucket.org/%7B6ae3c307-ae59-4135-9c72-bdd06eb2010a%7D/"},
                    "avatar": {
                        "href": "https://secure.gravatar.com/avatar/ac4da70f6b5f883c3d6fb67359182b62?d=https%3A%2F%2Favatar-management--avatars.us-west-2.prod.public.atl-paas.net%2Finitials%2FAF-1.png"
                    },
                },
                "type": "user",
                "nickname": "Asher Foa",
                "account_id": "6059303e630024006fab8c2b",
            },
        }

    def test_get_non_existent_push(self, client) -> None:
        response = client.get("/api/v1/bitbucket/mail/newman/push/tag/feats-of-strength/d3b233878c4/")
        assert response.status_code == 404
        assert response.content == b'{"detail":"Not found."}'
