# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

import pytest

from toolchain.base.datetime_tools import utcnow
from toolchain.bitbucket_integration.common.events import AppInstallEvent, AppUninstallEvent
from toolchain.bitbucket_integration.models import BitbucketAppInstall


@pytest.mark.django_db()
class TestBitbucketAppInstall:
    @pytest.fixture()
    def app_install_event(self) -> AppInstallEvent:
        return AppInstallEvent(
            account_name="bagels",
            account_id="h&h",
            account_type="team",
            account_url="https:/no-soup-for.you",
            client_key="no-bagels",
            shared_secret="Yama Hama it's Fright Night.",
            jwt="moles",
        )

    @pytest.fixture()
    def app_uninstall_event(self) -> AppUninstallEvent:
        return AppUninstallEvent(
            account_name="No Bagels",
            account_id="h&h",
            account_type="team",
            account_url="https:/no-soup-for.you",
            client_key="no-bagels",
            jwt="moles",
        )

    def assert_app_install(self, app_install: BitbucketAppInstall, account_name: str = "bagels") -> None:
        assert app_install.customer_id == "kramer"
        assert app_install.account_id == "h&h"
        assert app_install.account_name == account_name
        assert app_install.client_key == "no-bagels"
        assert app_install.shared_secret == "Yama Hama it's Fright Night."
        assert app_install.app_state == BitbucketAppInstall.State.INSTALLED

    def test_install_new(self, app_install_event: AppInstallEvent) -> None:
        assert BitbucketAppInstall.objects.count() == 0
        now_ts = utcnow().timestamp()

        obj = BitbucketAppInstall.install(
            customer_id="kramer", app_install=app_install_event, account_name=app_install_event.account_name
        )
        assert BitbucketAppInstall.objects.count() == 1
        loaded = BitbucketAppInstall.objects.first()
        assert loaded == obj
        self.assert_app_install(loaded)

        assert loaded.created_at.timestamp() == pytest.approx(now_ts)
        assert loaded.last_updated.timestamp() == pytest.approx(now_ts)

    def test_install_existing(self, app_install_event: AppInstallEvent) -> None:
        BitbucketAppInstall.objects.create(
            customer_id="kramer",
            account_name="Bagels",
            account_id="h&h",
            client_key="bagels-bagels",
            shared_secret="Happy Festivus",
            created_at=datetime.datetime(2020, 7, 10, tzinfo=datetime.timezone.utc),
        )
        now_ts = utcnow().timestamp()
        obj = BitbucketAppInstall.install(customer_id="kramer", app_install=app_install_event, account_name="No-Bagels")
        assert BitbucketAppInstall.objects.count() == 1
        loaded = BitbucketAppInstall.objects.first()
        assert loaded == obj
        self.assert_app_install(loaded, account_name="No-Bagels")
        assert loaded.created_at == datetime.datetime(2020, 7, 10, tzinfo=datetime.timezone.utc)
        assert loaded.last_updated.timestamp() == pytest.approx(now_ts)

    def test_install_uninstall_not_existing(self, app_uninstall_event: AppUninstallEvent) -> None:
        assert BitbucketAppInstall.objects.count() == 0
        result = BitbucketAppInstall.uninstall(customer_id="kramer", app_uninstall=app_uninstall_event)
        assert result is False
        assert BitbucketAppInstall.objects.count() == 0

    def test_install_uninstall_mismatch_account_id(self, app_uninstall_event: AppUninstallEvent) -> None:
        obj = BitbucketAppInstall.objects.create(
            customer_id="kramer",
            account_name="No-Bagels",
            account_id="festivus-for-the-rest-of-us",
            client_key="bagels-bagels",
            shared_secret="Happy Festivus",
        )
        assert BitbucketAppInstall.objects.count() == 1
        result = BitbucketAppInstall.uninstall(customer_id="kramer", app_uninstall=app_uninstall_event)
        assert result is False
        assert BitbucketAppInstall.objects.count() == 1
        loaded = BitbucketAppInstall.objects.first()
        assert loaded == obj
        assert loaded.customer_id == "kramer"
        assert loaded.account_id == "festivus-for-the-rest-of-us"
        assert loaded.account_name == "No-Bagels"
        assert loaded.client_key == "bagels-bagels"
        assert loaded.app_state == BitbucketAppInstall.State.INSTALLED

    def test_install_uninstall_mismatch_client_key(self, app_uninstall_event: AppUninstallEvent) -> None:
        obj = BitbucketAppInstall.objects.create(
            customer_id="kramer",
            account_name="No-Bagels",
            account_id="h&h",
            client_key="feats-of-strength",
            shared_secret="Happy Festivus",
        )
        assert BitbucketAppInstall.objects.count() == 1
        result = BitbucketAppInstall.uninstall(customer_id="kramer", app_uninstall=app_uninstall_event)
        assert result is False
        assert BitbucketAppInstall.objects.count() == 1
        loaded = BitbucketAppInstall.objects.first()
        assert loaded == obj
        assert loaded.customer_id == "kramer"
        assert loaded.account_id == "h&h"
        assert loaded.account_name == "No-Bagels"
        assert loaded.client_key == "feats-of-strength"
        assert loaded.app_state == BitbucketAppInstall.State.INSTALLED

    def test_install_uninstall(self, app_uninstall_event: AppUninstallEvent) -> None:
        obj = BitbucketAppInstall.objects.create(
            customer_id="kramer",
            account_name="bagels",
            account_id="h&h",
            client_key="no-bagels",
            shared_secret="Happy Festivus",
            created_at=datetime.datetime(2020, 7, 23, tzinfo=datetime.timezone.utc),
        )
        assert BitbucketAppInstall.objects.count() == 1
        now_ts = utcnow().timestamp()
        result = BitbucketAppInstall.uninstall(customer_id="kramer", app_uninstall=app_uninstall_event)
        assert result is True
        assert BitbucketAppInstall.objects.count() == 1
        loaded = BitbucketAppInstall.objects.first()
        assert loaded == obj
        assert loaded.customer_id == "kramer"
        assert loaded.account_id == "h&h"
        assert loaded.account_name == "No Bagels"
        assert loaded.client_key == "no-bagels"
        assert loaded.app_state == BitbucketAppInstall.State.UNINSTALLED
        assert loaded.created_at == datetime.datetime(2020, 7, 23, tzinfo=datetime.timezone.utc)
        assert loaded.last_updated.timestamp() == pytest.approx(now_ts)
