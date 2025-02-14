# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json

import pytest

from toolchain.notifications.email.test_utils.utils import load_fixture
from toolchain.util.test.util import assert_messages, convert_headers_to_wsgi


class TestAwsSesWebhookView:
    def _post_rejected_test_hook(
        self,
        caplog,
        client,
        payload: dict,
        headers: dict,
        reject_error: str,
    ):
        content_type = headers.pop("Content-Type")
        response = client.post(
            "/aws/ses/",
            content_type=content_type,
            data=json.dumps(payload).encode(),
            **convert_headers_to_wsgi(headers),
        )
        assert response.status_code == 200
        assert_messages(caplog, match=f"reject_aws_ses_webhook reason={reject_error}")

    def test_ses_webhook(self, client, caplog) -> None:
        fixture = load_fixture("aws_ses_webhook")
        headers = fixture["headers"]
        content_type = headers.pop("Content-Type")
        response = client.post(
            "/aws/ses/", content_type=content_type, data=fixture["body"].encode(), **convert_headers_to_wsgi(headers)
        )
        assert response.status_code == 200
        assert_messages(caplog, match="Got AWS SES webhook")

    def test_sns_subscription_confirmation(self, client, caplog) -> None:
        fixture = load_fixture("sns_subscription_confirmation")
        headers = fixture["headers"]
        content_type = headers.pop("Content-Type")
        response = client.post(
            "/aws/ses/", content_type=content_type, data=fixture["body"].encode(), **convert_headers_to_wsgi(headers)
        )
        assert response.status_code == 200
        assert_messages(caplog, match="sns_subscription_confirmation: https://sns.us-east-1.amazonaws.com/")

    @pytest.mark.parametrize("method", ["GET", "HEAD", "DELETE", "PATCH", "PUT"])
    def test_ses_webhook_invalid_method(self, client, method: str) -> None:
        response = client.generic(method, "/aws/ses/")
        assert response.status_code == 405

    def test_reject_webhook_no_type(self, client, caplog) -> None:
        fixture = load_fixture("sns_subscription_confirmation")
        payload = json.loads(fixture["body"])
        del payload["Type"]
        self._post_rejected_test_hook(
            caplog, client, payload, headers=fixture["headers"], reject_error="'invalid_json_body'.*KeyError"
        )

    def test_reject_webhook_no_signature(self, client, caplog) -> None:
        fixture = load_fixture("sns_subscription_confirmation")
        payload = json.loads(fixture["body"])
        del payload["Signature"]
        self._post_rejected_test_hook(
            caplog,
            client,
            payload,
            headers=fixture["headers"],
            reject_error="'signature_verification_failed'.*Missing Signature field",
        )

    def test_reject_webhook_no_signature_version(self, client, caplog) -> None:
        fixture = load_fixture("sns_subscription_confirmation")
        payload = json.loads(fixture["body"])
        del payload["SignatureVersion"]
        self._post_rejected_test_hook(
            caplog,
            client,
            payload,
            headers=fixture["headers"],
            reject_error="'signature_verification_failed'.*Invalid SignatureVersion",
        )

    def test_reject_webhook_invalid_signature_version(self, client, caplog) -> None:
        fixture = load_fixture("sns_subscription_confirmation")
        payload = json.loads(fixture["body"])
        payload["SignatureVersion"] = "22"
        self._post_rejected_test_hook(
            caplog,
            client,
            payload,
            headers=fixture["headers"],
            reject_error="'signature_verification_failed'.*Invalid SignatureVersion",
        )

    def test_reject_webhook_missing_signed_field(self, client, caplog) -> None:
        fixture = load_fixture("sns_subscription_confirmation")
        payload = json.loads(fixture["body"])
        del payload["MessageId"]
        self._post_rejected_test_hook(
            caplog,
            client,
            payload,
            headers=fixture["headers"],
            reject_error="'signature_verification_failed'.*missing field",
        )

    def test_reject_webhook_unknown_notifcation_type(self, client, caplog) -> None:
        fixture = load_fixture("sns_subscription_confirmation")
        payload = json.loads(fixture["body"])
        payload["Type"] = "puddy"
        self._post_rejected_test_hook(
            caplog,
            client,
            payload,
            headers=fixture["headers"],
            reject_error="'signature_verification_failed'.*Invalid notification type",
        )

    def test_reject_webhook_invalid_cert_url(self, client, caplog) -> None:
        fixture = load_fixture("sns_subscription_confirmation")
        payload = json.loads(fixture["body"])
        payload["SigningCertURL"] = "https//evil.jerry.com/puddy"
        self._post_rejected_test_hook(
            caplog,
            client,
            payload,
            headers=fixture["headers"],
            reject_error="'signature_verification_failed'.*Unexpected SigningCertURL",
        )
