# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.notifications.email.models import EmailMessageRequest, SentEmailMessage


@pytest.mark.django_db()
class TestEmailMessageRequest:
    def test_create(self):
        assert EmailMessageRequest.objects.count() == 0
        emr = EmailMessageRequest.create_request(
            topic_name="Festivus",
            recipient_user_api_id="featsofstrength",
            message_key="jerry",
            context_data={
                "newman_partition_1": "soup",
                "newman_partition_2": "pool",
                "newman_id": "crazy",
                "newman_timestamp": 921,
            },
        )
        assert EmailMessageRequest.objects.count() == 1
        loaded = EmailMessageRequest.objects.first()
        assert emr.created_at == loaded.created_at
        assert emr.id == loaded.id
        # assert emr.created_at == pytest.approx(utcnow(), abs=datetime.timedelta(seconds=1))
        assert loaded.status == emr.status == EmailMessageRequest.Status.QUEUED
        assert loaded.topic_name == emr.topic_name == "Festivus"
        assert (
            loaded.context_data
            == emr.context_data
            == {
                "newman_partition_1": "soup",
                "newman_partition_2": "pool",
                "newman_id": "crazy",
                "newman_timestamp": 921,
            }
        )
        assert loaded.message_key == emr.message_key == "jerry"
        assert loaded.recipient_user_api_id == emr.recipient_user_api_id == "featsofstrength"


@pytest.mark.django_db()
class TestSentEmailMessage:
    @pytest.fixture()
    def msg_req(self) -> EmailMessageRequest:
        return EmailMessageRequest.create_request(
            topic_name="Festivus",
            recipient_user_api_id="featsofstrength",
            message_key="jerry",
            context_data={
                "newman_partition_1": "soup",
                "newman_partition_2": "pool",
                "newman_id": "crazy",
                "newman_timestamp": 921,
            },
        )

    def test_create(self, msg_req: EmailMessageRequest) -> None:
        assert SentEmailMessage.objects.count() == 0
        sem = SentEmailMessage.create(
            req_msg=msg_req,
            to_email="jerry@seinfeld.nbc",
            recipient_user_api_id="newman882",
            subject="I choose not to run!",
            s3_url="s3://festivus.bucket.local/david/puddy/message.html",
        )
        assert SentEmailMessage.objects.count() == 1
        loaded = SentEmailMessage.objects.first()
        assert loaded.created_at == sem.created_at
        assert loaded.id == sem.id
        assert loaded.requested_message_id == sem.requested_message_id == msg_req.id
        assert loaded.to == sem.to == "jerry@seinfeld.nbc"
        assert loaded.recipient_user_api_id == sem.recipient_user_api_id == "newman882"
        assert loaded.subject == sem.subject == "I choose not to run!"
        assert (
            loaded.rendered_email_s3_url
            == sem.rendered_email_s3_url
            == "s3://festivus.bucket.local/david/puddy/message.html"
        )
        assert loaded.to == sem.to == "jerry@seinfeld.nbc"
        assert loaded.status == sem.status == SentEmailMessage.Status.PRE_SEND
        assert loaded.provider == sem.provider == SentEmailMessage.Provider.AWS_SES
