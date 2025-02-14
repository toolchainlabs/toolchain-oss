# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import getpass
import json
import logging
import socket
from dataclasses import dataclass
from enum import Enum, unique

import httpx

from toolchain.aws.secretsmanager import SecretsManager
from toolchain.base.toolchain_error import ToolchainAssertion

_logger = logging.getLogger(__name__)


@unique
class Channel(Enum):
    GENERAL = "general"
    BOTS = "bots"
    ALERTS = "alerts-manager-test"
    DEVOPS = "devops"
    FRONTEND = "frontend"
    BACKEND = "backend"


@unique
class Severity(Enum):
    CRITICAL = "danger"  # green
    INFO = "#439FE0"  # light blue
    OK = "good"  # red
    WARNING = "warning"  # yellow


@dataclass(frozen=True)
class MessageLinks:
    title: str
    links: tuple[tuple[str, str], ...]


class ChatClient:
    Severity = Severity
    Channel = Channel

    @classmethod
    def for_django_service(cls, django_settings) -> ChatClient:
        title = "Toolchain Services"
        sender = django_settings.SERVICE_INFO.name
        webhook = django_settings.SLACK_WEBHOOK
        return cls(title=title, sender_type="Service", sender=sender, webhook_url=webhook)

    @classmethod
    def for_devops(cls, aws_region: str, user: str = "") -> ChatClient:
        secrets_mgr = SecretsManager(region=aws_region)
        secret = secrets_mgr.get_secret("SlackDevopsNotifications")
        if not secret:
            raise ToolchainAssertion("Failed to load slack webhook secret")
        user = user or f"{getpass.getuser()} @ {socket.gethostname()}"
        return cls(
            title="Toolchain DevOps",
            sender_type="User",
            sender=user,
            webhook_url=json.loads(secret)["slack_devops_webhook"],
        )

    @classmethod
    def for_job(cls, job_name: str, webhook_url: str) -> ChatClient:
        return cls(title=job_name, sender_type=None, sender=None, webhook_url=webhook_url)

    def __init__(self, title: str, sender_type: str | None, sender: str | None, webhook_url: str) -> None:
        self._webhook = webhook_url
        self._sender_type = sender_type
        self._sender = sender
        self._title = title

    def _format_links_list(self, msg_links: MessageLinks) -> dict:
        lines = [f"• <{link}|{text}>" for text, link in msg_links.links]
        return {
            "blocks": [
                {"type": "divider"},
                {"type": "section", "text": {"type": "mrkdwn", "text": msg_links.title}},
                {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}},
            ]
        }

    def post_message(self, message: str, channel: Channel, serverity: Severity = Severity.INFO, emoji: str | None = None, msg_links: MessageLinks | None = None):  # type: ignore
        # https://api.slack.com/docs/message-formatting
        data = {
            "channel": channel.value,  # type: ignore
            "attachments": [
                {
                    "color": serverity.value,  # type: ignore
                    "fields": [{"title": self._sender_type, "value": self._sender}] if self._sender_type else [],
                    "title": self._title,
                    "text": message,
                }
            ],
        }
        if emoji:
            data["icon_emoji"] = f":{emoji}:"
        if msg_links:
            data["attachments"].append(self._format_links_list(msg_links))
        response = httpx.post(self._webhook, json=data)
        if response.is_error:
            _logger.warning(f"post message failed: {response.status_code} -- {response.text}")
