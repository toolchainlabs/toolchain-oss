# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import base64
import json
import logging
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.padding import PKCS1v15
from cryptography.hazmat.primitives.hashes import SHA1
from django.conf import settings
from django.http import HttpResponse
from django.views.generic import View

from toolchain.base.toolchain_error import ToolchainError

_logger = logging.getLogger(__name__)


class SignatureVerificationError(ToolchainError):
    pass


class AwsSesWebhookView(View):
    view_type = "app"
    CAMEL_TO_SNAKE_CASE = re.compile(r"(?<!^)(?=[A-Z])")

    def _handle_notification(self, sns_notification: dict) -> HttpResponse:
        try:
            message = json.loads(sns_notification["Message"])
            notification_type = message["notificationType"]
            mail_id = message["mail"]["messageId"]
        except (KeyError, ValueError) as error:
            return self._reject_webhook(reason="can't decode json body", error_details=repr(error))
        _logger.info(f"Got AWS SES webhook {notification_type=} {mail_id=}")
        return HttpResponse()

    def _handle_subscription_confirmation(self, sns_notification: dict) -> HttpResponse:
        subscribe_url = sns_notification.get("SubscribeURL")
        if not subscribe_url:
            return self._reject_webhook(
                reason="no SubscribeURL in subscription confirmation", error_details=str(sns_notification)
            )
        _logger.info(f"sns_subscription_confirmation: {subscribe_url}")
        return HttpResponse()

    def _reject_webhook(self, reason: str, error_details: str) -> HttpResponse:
        _logger.warning(f"reject_aws_ses_webhook {reason=} {error_details}")
        return HttpResponse()

    def post(self, request) -> HttpResponse:
        # aws_sns_msg_id = request.headers.get("X-Amz-Sns-Message-Id")
        # https://docs.aws.amazon.com/ses/latest/dg/configure-sns-notifications.html#configure-feedback-notifications-console
        try:
            sns_notification = json.loads(request.body)
            sns_notification_type = sns_notification["Type"]
        except (ValueError, KeyError) as error:
            return self._reject_webhook(reason="invalid_json_body", error_details=repr(error))
        try:
            valid_sns_message(sns_notification, certificate=settings.AWS_SNS_CERT)
        except SignatureVerificationError as error:
            return self._reject_webhook(reason="signature_verification_failed", error_details=repr(error))
        method_name = f"_handle_{self.CAMEL_TO_SNAKE_CASE.sub('_',sns_notification_type).lower()}"
        handler = getattr(self, method_name, None)
        if not handler:
            return self._reject_webhook(
                reason="no_handler", error_details=f"notification type: {sns_notification_type} {method_name=}"
            )
        return handler(sns_notification)


_EXPECTED_CERT_URL = (
    "https://sns.us-east-1.amazonaws.com/SimpleNotificationService-7ff5318490ec183fbaddaa2a969abfda.pem"
)
_NOTIFICATION_TYPES = frozenset(["SubscriptionConfirmation", "Notification", "UnsubscribeConfirmation"])
_FIELDS_BY_NOTIFICATION = {
    "SubscriptionConfirmation": ("Message", "MessageId", "SubscribeURL", "Timestamp", "Token", "TopicArn", "Type"),
    "UnsubscribeConfirmation": ("Message", "MessageId", "SubscribeURL", "Timestamp", "Token", "TopicArn", "Type"),
    "Notification": ("Message", "MessageId", "Subject", "Timestamp", "TopicArn", "Type"),
}


def valid_sns_message(sns_payload, certificate):
    # https://docs.aws.amazon.com/sns/latest/dg/sns-verify-signature-of-message.html
    # https://github.com/boto/boto3/issues/2508#issuecomment-657780203
    # https://github.com/wlwg/aws-sns-message-validator/blob/master/sns_message_validator/sns_message_validator.py
    # Can only be one of these types.
    notification_type = sns_payload.get("Type", "missing_notification_type")

    if notification_type not in _NOTIFICATION_TYPES:
        raise SignatureVerificationError(f"Invalid notification type: {notification_type}")

    # Amazon SNS currently supports signature version 1.
    version = sns_payload.get("SignatureVersion", "missing_signature_version")
    if version != "1":
        raise SignatureVerificationError(f"Invalid SignatureVersion. {version=}")
    fields = _FIELDS_BY_NOTIFICATION[notification_type]

    # Build the string to be signed.
    string_to_sign = ""
    for field in fields:
        if field not in sns_payload:
            if field == "Subject":
                continue
            raise SignatureVerificationError(f"missing field {field=} in payload. fields {sns_payload.keys()}.")
        string_to_sign += field + "\n" + sns_payload[field] + "\n"

    if "Signature" not in sns_payload:
        raise SignatureVerificationError(f"Missing Signature field. {sns_payload.keys()}")
    # Decode the signature from base64.
    decoded_signature = base64.b64decode(sns_payload["Signature"])
    cert_url = sns_payload.get("SigningCertURL", "no_cert_url")
    if cert_url != _EXPECTED_CERT_URL:
        raise SignatureVerificationError(f"Unexpected SigningCertURL. {cert_url}")
    public_key = certificate.public_key()
    try:
        public_key.verify(decoded_signature, string_to_sign.encode(), PKCS1v15(), SHA1())
    except InvalidSignature as error:
        raise SignatureVerificationError(f"Invalid signature. {error!r}")
