# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime
import textwrap

import boto3
import pytest
from freezegun import freeze_time
from moto import mock_iam, mock_ses
from moto.core import DEFAULT_ACCOUNT_ID
from moto.iam.models import iam_backends

from toolchain.aws.test_utils.common import TEST_REGION
from toolchain.aws.test_utils.ses_utils import get_ses_sent_messages, get_ses_sent_messages_count, verify_ses_email
from toolchain.base.datetime_tools import utcnow
from toolchain.prod.iam_watcher.check_iam_access_keys import IAMAccessKeysWatcher


@pytest.fixture(autouse=True)
def _start_moto():
    with mock_iam(), mock_ses():
        verify_ses_email("ops@toolchain.com")
        yield


@pytest.fixture()
def watcher():
    return IAMAccessKeysWatcher.create_for_args(aws_region=TEST_REGION)


def _create_fake_iam_user(username, key_date=None, email_tag=None):
    iam = boto3.client("iam")
    if email_tag:
        iam.create_user(UserName=username, Tags=[{"Key": "notify_emails", "Value": email_tag}])
    else:
        iam.create_user(UserName=username)
    if key_date:
        iam.create_access_key(UserName=username)
        access_key = iam_backends[DEFAULT_ACCOUNT_ID]["global"].users[username].access_keys[0]
        access_key.create_date = key_date


def test_no_op_no_users(watcher):
    notified, deleted = watcher.check_iam_creds(
        notify_age=datetime.timedelta(days=3), delete_age=datetime.timedelta(days=30)
    )
    assert notified == 0
    assert deleted == 0


def _assert_notify_message(message, username, days, destinations, delete_on_date):
    assert message.source == "ops@toolchain.com"
    assert message.subject == f"IAM User {username} has old access keys."
    expected_body = textwrap.dedent(
        f"""
        Please generate a new AWS IAM Access key.
        You can run `./pants run src/python/toolchain/prod/aws_creds:rotate-aws-creds` to rotate your access key.
        <br/><br/>
        (Keys will be automatically deleted if they are older than {days} days on {delete_on_date}.)
        """
    )
    assert message.body == expected_body
    assert message.destinations == {"BccAddresses": [], "CcAddresses": [], "ToAddresses": destinations}


@freeze_time(datetime.datetime(2021, 5, 2, 16, 3, tzinfo=datetime.timezone.utc))
def test_notify_users_with_email_tag(watcher):
    now = utcnow()
    _create_fake_iam_user("jerry", key_date=now - datetime.timedelta(days=8), email_tag="david@puddy.com")
    notified, deleted = watcher.check_iam_creds(
        notify_age=datetime.timedelta(days=3), delete_age=datetime.timedelta(days=30)
    )
    assert notified == 1
    assert deleted == 0
    assert get_ses_sent_messages_count() == 1
    _assert_notify_message(
        get_ses_sent_messages()[0],
        username="jerry",
        days=30,
        destinations=["david@puddy.com"],
        delete_on_date="2021-05-24",
    )


@freeze_time(datetime.datetime(2021, 5, 2, 16, 3, tzinfo=datetime.timezone.utc))
def test_notify_user_default_email(watcher):
    now = utcnow()
    _create_fake_iam_user("jackie", key_date=now - datetime.timedelta(days=8))
    notified, deleted = watcher.check_iam_creds(
        notify_age=datetime.timedelta(days=3), delete_age=datetime.timedelta(days=88)
    )
    assert notified == 1
    assert deleted == 0
    assert get_ses_sent_messages_count() == 1
    _assert_notify_message(
        get_ses_sent_messages()[0],
        username="jackie",
        days=88,
        destinations=["jackie@toolchain.com"],
        delete_on_date="2021-07-21",
    )
