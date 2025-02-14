# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from jinja2 import Environment, FileSystemLoader, select_autoescape

from toolchain.aws.s3 import S3
from toolchain.aws.ses import SES
from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainError
from toolchain.django.site.models import ToolchainUser
from toolchain.notifications.email.models import EmailMessageRequest, ProcessEmailMessageRequest, SentEmailMessage
from toolchain.notifications.email.topic import Topic
from toolchain.workflow.config import WorkflowWorkerConfig
from toolchain.workflow.work_dispatcher import WorkDispatcher
from toolchain.workflow.worker import Worker

_logger = logging.getLogger(__name__)

DUPLICATE = object()


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    body_html: str


class EmailSentFailure(ToolchainError):
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


class EmailProcessor(Worker):
    work_unit_payload_cls = ProcessEmailMessageRequest

    _S3_BUCKET = settings.RENDER_EMAIL_S3_BUCKET
    _S3_BASE_PATH = settings.RENDER_EMAIL_S3_BASE_PATH

    def do_work(self, work_unit_payload: ProcessEmailMessageRequest) -> bool:
        msg_req = EmailMessageRequest.objects.get(id=work_unit_payload.requested_message_id)
        self.process_message_for_sending(msg_req)
        return True

    def process_message_for_sending(self, email_message: EmailMessageRequest) -> SentEmailMessage | None:
        recipient_user = ToolchainUser.get_by_api_id(api_id=email_message.recipient_user_api_id)
        if not recipient_user:
            email_message.mark_user_not_active()
            return None
        to_email_addr = recipient_user.email
        topic = Topic.get_topic(email_message.topic_name, user=recipient_user, context=email_message.context_data)

        # Check for duplicated emails.
        last_message = EmailMessageRequest.get_latest_sent_message(
            topic_name=email_message.topic_name,
            message_key=email_message.message_key,
            recipient_user_api_id=email_message.recipient_user_api_id,
        )
        if last_message and last_message.created_at > utcnow() - topic.max_frequency():
            _logger.info(
                f"message {email_message} exceeds max frequency, last request: {last_message.created_at} {last_message=}. marking is duplicate"
            )
            email_message.mark_duplicate()
            return None

        rendered = render_email_message(topic)
        s3_url = self._store_email(email_message, recipient_user, rendered_email=rendered)
        sent_email_message = SentEmailMessage.create(
            req_msg=email_message,
            to_email=to_email_addr,
            recipient_user_api_id=recipient_user.api_id,
            subject=rendered.subject,
            s3_url=s3_url,
        )

        try:
            external_id = send_email_message(to_email_addr, rendered)  # TODO: handle failure cases
        except EmailSentFailure as error:
            sent_email_message.send_failure(error.reason)
        else:
            sent_email_message.email_sent(external_id)

        return sent_email_message

    def _store_email(
        self, email_message: EmailMessageRequest, recipient_user: ToolchainUser, rendered_email: RenderedEmail
    ) -> str:
        s3 = S3()
        key_path = (
            self._S3_BASE_PATH
            / recipient_user.api_id
            / email_message.topic_name
            / f"{email_message.topic_name}_{email_message.id}.html"
        )
        s3.upload_content(
            bucket=self._S3_BUCKET,
            key=key_path.as_posix(),
            content_bytes=rendered_email.body_html.encode(),
            content_type="application/html",
        )
        return s3.get_s3_url(bucket=self._S3_BUCKET, key=key_path.as_posix())


def send_email_message(to: str, email: RenderedEmail) -> str:
    # TODO: catch & handle errors.
    msg_id = SES().send_html_email(
        from_email="noreply@toolchain.com", to_emails=[to], subject=email.subject, html_content=email.body_html
    )
    return msg_id


def render_email_message(topic: Topic) -> RenderedEmail:
    # TODO: add support for list-unsubscribe RFC 2369
    # https://datatracker.ietf.org/doc/html/rfc2369
    template_name = topic.template_name()
    subject = topic.get_subject()
    loader = FileSystemLoader(Path(__file__).parent / "email_templates")
    jinja_env = Environment(loader=loader, autoescape=select_autoescape(["html"]))
    template = jinja_env.get_template(template_name)
    context = {"unsubscribe_link": "tbd", "view_in_browser_link": "tbd"}
    context.update(topic.context_data)
    html_content = template.render(context)
    _logger.info(f"Render: {template_name} {len(html_content):,} bytes.")
    return RenderedEmail(subject=subject, body_html=html_content)


class EmailWorkDispatcher(WorkDispatcher):
    worker_classes = (EmailProcessor,)

    @classmethod
    def for_django(cls, config: WorkflowWorkerConfig) -> EmailWorkDispatcher:
        return cls.for_worker_classes(config=config, worker_classes=cls.worker_classes)
