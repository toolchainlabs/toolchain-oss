# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from enum import Enum, unique

import shortuuid
from django.db.models import CASCADE, CharField, DateTimeField, EmailField, ForeignKey, JSONField

from toolchain.base.datetime_tools import utcnow
from toolchain.django.db.base_models import ToolchainModel
from toolchain.django.util.helpers import get_choices
from toolchain.notifications.email.topics import DummyEmailTopic
from toolchain.workflow.models import WorkUnitPayload

tpcs = (DummyEmailTopic,)

_logger = logging.getLogger(__name__)


class EmailMessageRequestStatus(Enum):
    QUEUED = "QUEUED"
    DUPLICATE = "DUPLICATE"
    USER_NA = "USER_NA"
    SENDING = "SENDING"


class EmailMessageRequest(ToolchainModel):
    Status = EmailMessageRequestStatus

    id = CharField(max_length=22, primary_key=True, default=shortuuid.uuid, editable=False)
    topic_name = CharField(max_length=64)
    recipient_user_api_id = CharField(max_length=22)
    message_key = CharField(max_length=256)
    context_data = JSONField()
    _status = CharField(
        max_length=16,
        db_column="status",
        default=EmailMessageRequestStatus.QUEUED.value,
        choices=get_choices(EmailMessageRequestStatus),
    )
    created_at = DateTimeField(default=utcnow)

    @classmethod
    def create_request(
        cls, *, recipient_user_api_id: str, topic_name: str, message_key: str, context_data: dict
    ) -> EmailMessageRequest:
        obj = cls.objects.create(
            topic_name=topic_name,
            message_key=message_key,
            context_data=context_data,
            recipient_user_api_id=recipient_user_api_id,
        )
        _logger.info(f"created {obj}")
        return obj

    @property
    def status(self) -> EmailMessageRequestStatus:
        return EmailMessageRequestStatus(self._status)

    def mark_duplicate(self) -> None:
        self._status = EmailMessageRequestStatus.DUPLICATE.value
        self.save()

    def mark_user_not_active(self) -> None:
        self._status = EmailMessageRequestStatus.USER_NA.value
        self.save()

    def __str__(self) -> str:
        return f"email message request topic={self.topic_name} key={self.message_key} id={self.id} recipient={self.recipient_user_api_id} status={self.status.value}"

    @classmethod
    def get_latest_sent_message(
        cls, *, topic_name: str, message_key: str, recipient_user_api_id: str
    ) -> EmailMessageRequest | None:
        """Returns the most recent message for a duplicate message.

        A duplicate is a message with the same `topic`, `recipient`, and `message_key`. Each topic defines a threshold
        for how frequently duplicated messages may be sent.
        """

        qs = cls.objects.filter(
            topic_name=topic_name,
            recipient_user_api_id=recipient_user_api_id,
            message_key=message_key,
            _status=EmailMessageRequestStatus.SENDING.value,
        )
        return qs.order_by("-created_at").first()


@unique
class SentEmailMessageStatus(Enum):
    PRE_SEND = "PRE_SEND"
    IN_FLIGHT = "IN_FLIGHT"
    FAILED = "FAILED"
    COMPLETE = "COMPLETE"


@unique
class EmailProvider(Enum):
    AWS_SES = "ses"
    SENDGRID = "sendgrid"


class SentEmailMessage(ToolchainModel):
    Status = SentEmailMessageStatus
    Provider = EmailProvider

    id = CharField(max_length=22, primary_key=True, default=shortuuid.uuid, editable=False)
    requested_message = ForeignKey(EmailMessageRequest, on_delete=CASCADE)
    to = EmailField()  # recipient email address
    recipient_user_api_id = CharField(max_length=22)
    subject = CharField(max_length=512)
    created_at = DateTimeField(default=utcnow)
    rendered_email_s3_url = CharField(max_length=512)

    _status = CharField(
        max_length=16,
        db_column="status",
        default=SentEmailMessageStatus.IN_FLIGHT.value,
        choices=get_choices(SentEmailMessageStatus),
    )
    _provider = CharField(
        max_length=10,
        db_column="provider",
        default=EmailProvider.AWS_SES.value,
        choices=get_choices(EmailProvider),
    )
    external_id = CharField(max_length=64, default="")  # value from the downstream API
    failure_reason = CharField(max_length=256, default="")  # Should only be non-empty if FAILED

    @classmethod
    def create(
        cls, req_msg: EmailMessageRequest, to_email: str, recipient_user_api_id: str, s3_url: str, subject: str
    ) -> SentEmailMessage:
        obj = cls.objects.create(
            requested_message=req_msg,
            to=to_email,
            _status=SentEmailMessageStatus.PRE_SEND.value,
            subject=subject,
            rendered_email_s3_url=s3_url,
            recipient_user_api_id=recipient_user_api_id,
        )
        return obj

    @property
    def status(self) -> SentEmailMessageStatus:
        return SentEmailMessageStatus(self._status)

    @property
    def provider(self) -> EmailProvider:
        return EmailProvider(self._provider)

    def send_failure(self, reason):
        self._status = SentEmailMessageStatus.FAILED.value
        self.failure_reason = reason
        self.save()

    def email_sent(self, external_id: str):
        self._status = SentEmailMessageStatus.IN_FLIGHT.value
        self.external_id = external_id
        self.save()


class ProcessEmailMessageRequest(WorkUnitPayload):
    requested_message_id = CharField(max_length=22, editable=False, unique=True)

    @classmethod
    def create(cls, msg_req: EmailMessageRequest) -> ProcessEmailMessageRequest:
        return cls.objects.create(requested_message_id=msg_req.id)
