# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime
from pathlib import Path
from unittest import mock

import pytest
from moto import mock_secretsmanager, mock_ses

from toolchain.aws.test_utils.common import TEST_REGION
from toolchain.aws.test_utils.ses_utils import get_ses_sent_messages, get_ses_sent_messages_count, verify_ses_email
from toolchain.prod.tools.deploy_notifications import (
    ChartDeployResults,
    Deployer,
    DeployNotifications,
    DeployType,
    FrontendDeployResult,
)
from toolchain.util.prod.chat_client_test import create_fake_slack_webhook_secret
from toolchain.util.prod.helm_charts import HelmChart
from toolchain.util.prod.helm_client import HelmExecuteResult


class TestDeployNotifications:
    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_ses(), mock_secretsmanager():
            create_fake_slack_webhook_secret()
            verify_ses_email("devinfra@toolchain.com")
            yield

    @pytest.fixture()
    def prod_notifications(self) -> DeployNotifications:
        return DeployNotifications(is_prod=True, aws_region=TEST_REGION, user="Kenny")

    def test_frontend_deploy_email(self, prod_notifications: DeployNotifications) -> None:
        deploy_result = FrontendDeployResult(
            deploy_type=DeployType.FRONTEND,
            app="festivus",
            deployer=Deployer(user="George Costanza", machine="glasses"),
            cluster=mock.MagicMock(value="night-guy"),
            namespace="morning-guy",
            dry_run=False,
            version="retail-is-for-suckers",
            bucket="commando-8",
            domain="rock-on",
            manifest_key="tunneling-to-the-center-of-the-earth",
            changes=(
                ("Look to the cookie", "https://seinfeld.com/cookie"),
                ("Marine Biologist", "https://seinfeld.com/costanza/george/"),
            ),
        )
        prod_notifications._email_deploy(prod_notifications._PROD_DEPLOY_EMAIL, deploy_result)
        assert get_ses_sent_messages_count() == 1
        msg = get_ses_sent_messages()[0]
        assert msg.subject == "Frontend deployed to night-guy/morning-guy"
        assert msg.source == "devinfra@toolchain.com"
        assert msg.destinations == {"ToAddresses": ["ops-notify@toolchain.com"], "CcAddresses": [], "BccAddresses": []}
        assert msg.body == (
            "\n<!DOCTYPE html>\n<head>\n"
            '  <meta charset="UTF-8">\n</head>\n<body>\n'
            "  <h2>Deployed Frontend into night-guy/morning-guy</h2>\n"
            "  <h4>Deployer: <b>George Costanza @ glasses</b></h4>\n  <p>\n"
            "    Version: retail-is-for-suckers <br/>\n"
            "    Domain: rock-on <br/>\n"
            "    Bucket: commando-8 <br/>\n"
            "    Manifest Key: tunneling-to-the-center-of-the-earth <br/>\n"
            "  </p>\n"
            "  <p>Deployed changes: </p>\n"
            "  <ul>\n"
            '    \n      <li><a href="https://seinfeld.com/cookie">Look to the cookie</a></li>\n'
            '    \n      <li><a href="https://seinfeld.com/costanza/george/">Marine Biologist</a></li>\n'
            "    \n  </ul>\n"
            "  <br />\n"
            "  <p>That is all.</p>\n</body>\n"
        )

    def test_frontend_deploy_email_missing_links(self, prod_notifications: DeployNotifications) -> None:
        deploy_result = FrontendDeployResult(
            deploy_type=DeployType.FRONTEND,
            deployer=Deployer(user="George Costanza", machine="glasses"),
            cluster=mock.MagicMock(value="night-guy"),
            namespace="morning-guy",
            dry_run=False,
            app="puddy",
            version="retail-is-for-suckers",
            bucket="commando-8",
            domain="rock-on",
            manifest_key="tunneling-to-the-center-of-the-earth",
            changes=(
                ("Look to the cookie", "https://seinfeld.com/cookie"),
                ("Importer/Exporter", None),
                ("Marine Biologist", "https://seinfeld.com/costanza/george/"),
            ),
        )
        prod_notifications._email_deploy(prod_notifications._PROD_DEPLOY_EMAIL, deploy_result)
        assert get_ses_sent_messages_count() == 1
        msg = get_ses_sent_messages()[0]
        assert msg.subject == "Frontend deployed to night-guy/morning-guy"
        assert msg.source == "devinfra@toolchain.com"
        assert msg.destinations == {"ToAddresses": ["ops-notify@toolchain.com"], "CcAddresses": [], "BccAddresses": []}
        assert msg.body == (
            "\n<!DOCTYPE html>\n<head>\n"
            '  <meta charset="UTF-8">\n</head>\n<body>\n'
            "  <h2>Deployed Frontend into night-guy/morning-guy</h2>\n"
            "  <h4>Deployer: <b>George Costanza @ glasses</b></h4>\n  <p>\n"
            "    Version: retail-is-for-suckers <br/>\n"
            "    Domain: rock-on <br/>\n"
            "    Bucket: commando-8 <br/>\n"
            "    Manifest Key: tunneling-to-the-center-of-the-earth <br/>\n"
            "  </p>\n"
            "  <p>Deployed changes: </p>\n"
            "  <ul>\n"
            '    \n      <li><a href="https://seinfeld.com/cookie">Look to the cookie</a></li>\n'
            "    \n      <li>Importer/Exporter</li>\n"
            '    \n      <li><a href="https://seinfeld.com/costanza/george/">Marine Biologist</a></li>\n'
            "    \n  </ul>\n"
            "  <br />\n"
            "  <p>That is all.</p>\n</body>\n"
        )

    def test_deploy_chart_email(self, prod_notifications: DeployNotifications) -> None:
        chart = HelmChart.for_path(Path("prod/helm/observability/logging"))
        exec_result = HelmExecuteResult(
            cluster=mock.MagicMock(value="running-from-a-bee"),
            namespace="basketball",
            command="perscription goggles",
            command_line="retail is for suckers",
            dry_run=False,
            success=True,
            output="rock on!",
            start=datetime.datetime(2020, 1, 1, 13, 34, tzinfo=datetime.timezone.utc),
            end=datetime.datetime(2020, 1, 1, 13, 39, tzinfo=datetime.timezone.utc),
        )
        deploy_result = ChartDeployResults.create(
            deployer=Deployer(user="George Costanza", machine="glasses"),
            chart=chart,
            deploy_time=datetime.datetime(2020, 1, 1, 13, 40, tzinfo=datetime.timezone.utc),
            exec_result=exec_result,
        )
        prod_notifications._email_deploy(prod_notifications._PROD_DEPLOY_EMAIL, deploy_result)
        assert get_ses_sent_messages_count() == 1
        msg = get_ses_sent_messages()[0]
        assert msg.subject == "Charts deployed to running-from-a-bee/basketball"
        assert msg.source == "devinfra@toolchain.com"
        assert msg.destinations == {"ToAddresses": ["ops-notify@toolchain.com"], "CcAddresses": [], "BccAddresses": []}
        assert msg.body == (
            "\n<!DOCTYPE html>\n<head>\n"
            '  <meta charset="UTF-8">\n</head>\n<body>\n'
            "  <h2>Installed Charts into running-from-a-bee/basketball</h2>\n"
            "  <h4>Deployer: <b>George Costanza @ glasses</b></h4>\n"
            "  <ul>\n    \n"
            "      <li>Chart: <b>logging</b> version: 3.6.0 Success: True Latency: 0:05:00\n        \n"
            "      </li>\n    \n  </ul>\n  <p>\n  <br />\n"
            "  <p>That is all.</p>\n</body>\n"
        )
