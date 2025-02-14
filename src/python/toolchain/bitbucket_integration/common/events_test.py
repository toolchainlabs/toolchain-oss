# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json

import pytest

from toolchain.bitbucket_integration.common.events import (
    AppInstallEvent,
    AppUninstallEvent,
    InvaliBitBucketEvent,
    WebhookEvent,
)
from toolchain.bitbucket_integration.test_utils.fixtures_loader import load_fixture, load_fixture_payload


class TestAppInstallEvent:
    def test_team_from_payload(self) -> None:
        payload = load_fixture_payload("app_install_team")
        app_install = AppInstallEvent.from_payload("bob", payload)
        assert app_install.account_name == "festivus-miracle"
        assert app_install.account_id == "{acf54878-51be-473e-bf0b-0fbb12e011ad}"
        assert app_install.client_key == "ari:cloud:bitbucket::app/{acf54878-51be-473e-bf0b-0fbb12e011ad}/toolchain-dev"
        assert app_install.shared_secret == "You can’t spare three squares?"
        assert app_install.jwt == "bob"


class TestAppUninstallEvent:
    def test_team_from_payload(self) -> None:
        payload = load_fixture_payload("app_uninstall_team")
        app_uninstall = AppUninstallEvent.from_payload("newman", payload)
        assert app_uninstall.account_name == "festivus-miracle"
        assert app_uninstall.account_id == "{acf54878-51be-473e-bf0b-0fbb12e011ad}"
        assert (
            app_uninstall.client_key == "ari:cloud:bitbucket::app/{acf54878-51be-473e-bf0b-0fbb12e011ad}/toolchain-dev"
        )
        assert app_uninstall.jwt == "newman"


class TestWebhookEvent:
    def test_create(self) -> None:
        fixture = load_fixture("pullrequest_created")
        body = json.dumps(fixture["payload"]).encode()
        event = WebhookEvent.create(headers=fixture["headers"], body=body)
        assert event.event_type == "pullrequest:created"
        assert event.event_id == "157c6eec-1118-410a-8ca6-6d9fcf399d87"
        assert event.hook_id == "1b08c6c1-a8d3-4b80-94e4-b9d64a98c385"
        assert (
            event.jwt
            == "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJhcmk6Y2xvdWQ6Yml0YnVja2V0OjphcHAve2FjZjU0ODc4LTUxYmUtNDczZS1iZjBiLTBmYmIxMmUwMTFhZH0vdG9vbGNoYWluLWRldiIsImlhdCI6MTYyNzUwODg2OCwicXNoIjoiZGJjZjRkY2FkYzIzNzNkNDRmZmYzOWZkOWVjZjk0NDI3OTIyMzgxNDRkMDI5YWEyNTAyZjYzYTliNmVkNjM5MyIsImF1ZCI6ImFyaTpjbG91ZDpiaXRidWNrZXQ6OmFwcC97YWNmNTQ4NzgtNTFiZS00NzNlLWJmMGItMGZiYjEyZTAxMWFkfS90b29sY2hhaW4tZGV2IiwiZXhwIjoxNjI3NTEyNDY4fQ.FiatdjQN3gF2_fZYlETTYArCCf9OA5mSSROHSKH0484"
        )
        assert event.attempt_number == 1
        assert event.json_payload == fixture["payload"]

    def test_no_jwt(self) -> None:
        fixture = load_fixture("pullrequest_created")
        headers = fixture["headers"]
        del headers["Authorization"]
        payload = json.dumps(fixture["payload"]).encode()
        with pytest.raises(InvaliBitBucketEvent, match="jwt_missing: headers="):
            WebhookEvent.create(headers=headers, body=payload)
