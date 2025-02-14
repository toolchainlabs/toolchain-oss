# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import pytest
from moto import mock_s3, mock_ses

from toolchain.aws.test_utils.s3_utils import create_s3_bucket
from toolchain.aws.test_utils.ses_utils import verify_ses_email
from toolchain.django.site.models import ToolchainUser
from toolchain.notifications.email.models import EmailMessageRequest, ProcessEmailMessageRequest
from toolchain.notifications.email.topics import DummyEmailTopic
from toolchain.notifications.email.worker import EmailWorkDispatcher
from toolchain.workflow.models import WorkUnit
from toolchain.workflow.tests_helper import BaseWorkflowWorkerTests
from toolchain.workflow.work_dispatcher import WorkDispatcher


class BaseWorkerTests(BaseWorkflowWorkerTests):
    def get_dispatcher(self) -> type[WorkDispatcher]:
        return EmailWorkDispatcher


class TestEmailProcessor(BaseWorkerTests):
    _BUCKET = "del-boca-vista-bucket"

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_s3(), mock_ses():
            verify_ses_email("noreply@toolchain.com")
            create_s3_bucket(self._BUCKET)
            yield

    @pytest.fixture()
    def user(self) -> ToolchainUser:
        return ToolchainUser.create(username="elaine", email="elaine@jerrysplace.com")

    def test_send_dummy_email(self, user: ToolchainUser) -> None:
        msg_req = EmailMessageRequest.create_request(
            topic_name=DummyEmailTopic.__name__,
            message_key="jerry",
            context_data={"title": "", "email_message_text": ""},
            recipient_user_api_id=user.api_id,
        )
        ProcessEmailMessageRequest.create(msg_req)
        assert self.do_work() == 1
        assert ProcessEmailMessageRequest.objects.count() == 1
        wu = ProcessEmailMessageRequest.objects.first().work_unit
        assert wu.state == WorkUnit.SUCCEEDED
