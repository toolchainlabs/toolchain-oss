# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json
from unittest import mock

import pytest
from moto import mock_secretsmanager

from toolchain.aws.test_utils.s3_utils import TEST_REGION
from toolchain.aws.test_utils.secrets import create_fake_secret
from toolchain.util.prod.chat_client import ChatClient


def create_fake_slack_webhook_secret():
    create_fake_secret(
        region=TEST_REGION,
        name="SlackDevopsNotifications",
        secret={"slack_devops_webhook": "https://fake.chat.puffy.local/tinesl/"},
    )


class TestChatClient:
    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_secretsmanager():
            create_fake_slack_webhook_secret()
            yield

    def test_send_message_from_service(self, httpx_mock) -> None:
        httpx_mock.add_response(method="POST", url="http://jerry.cluster.local.test/ovaltine")
        mock_svc_info = mock.MagicMock()
        mock_svc_info.name = "jerry/gold"
        chat = ChatClient.for_django_service(
            mock.MagicMock(SLACK_WEBHOOK="http://jerry.cluster.local.test/ovaltine", SERVICE_INFO=mock_svc_info)
        )
        chat.post_message("Gold jerry!! Gold", channel=chat.Channel.BOTS, serverity=chat.Severity.INFO)
        request = httpx_mock.get_request()
        assert request is not None
        assert request.url == "http://jerry.cluster.local.test/ovaltine"
        assert json.loads(request.read()) == {
            "channel": "bots",
            "attachments": [
                {
                    "color": "#439FE0",
                    "fields": [{"title": "Service", "value": "jerry/gold"}],
                    "title": "Toolchain Services",
                    "text": "Gold jerry!! Gold",
                }
            ],
        }

    def test_devops_send_message_with_emoji(self, httpx_mock) -> None:
        httpx_mock.add_response(method="POST", url="https://fake.chat.puffy.local/tinesl/")
        chat = ChatClient.for_devops(TEST_REGION, "mandelbaum")
        chat.post_message(
            "Cosmo got the caboose", channel=chat.Channel.DEVOPS, serverity=chat.Severity.CRITICAL, emoji="pole"
        )
        request = httpx_mock.get_request()
        assert request is not None
        assert request.url == "https://fake.chat.puffy.local/tinesl/"
        assert json.loads(request.read()) == {
            "channel": "devops",
            "icon_emoji": ":pole:",
            "attachments": [
                {
                    "color": "danger",
                    "fields": [{"title": "User", "value": "mandelbaum"}],
                    "title": "Toolchain DevOps",
                    "text": "Cosmo got the caboose",
                }
            ],
        }
