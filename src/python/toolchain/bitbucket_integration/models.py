# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from enum import Enum, unique

from django.db.models import CharField, DateTimeField

from toolchain.base.datetime_tools import utcnow
from toolchain.bitbucket_integration.common.events import AppInstallEvent, AppUninstallEvent
from toolchain.django.db.base_models import ToolchainModel
from toolchain.django.util.helpers import get_choices

_logger = logging.getLogger(__name__)


@unique
class AppInstallState(Enum):
    INSTALLED = "installed"
    UNINSTALLED = "uninstalled"


class BitbucketAppInstall(ToolchainModel):
    State = AppInstallState
    created_at = DateTimeField(default=utcnow, editable=False)
    last_updated = DateTimeField(default=utcnow)
    _app_state = CharField(
        max_length=15,
        default=AppInstallState.INSTALLED.value,
        db_index=True,
        null=False,
        db_column="app_state",
        choices=get_choices(AppInstallState),
    )

    customer_id = CharField(max_length=22)  # toolchain Customer.id

    # Fields from bitbucket payload
    client_key = CharField(max_length=128)
    shared_secret = CharField(max_length=128)
    account_name = CharField(max_length=64)  # principal.username
    account_id = CharField(max_length=64, primary_key=True, db_index=True, editable=False)  # principal.uuid

    @property
    def app_state(self) -> AppInstallState:
        return AppInstallState(self._app_state)

    @classmethod
    def for_account_id(cls, account_id: str) -> BitbucketAppInstall | None:
        return cls.get_or_none(account_id=account_id, _app_state=AppInstallState.INSTALLED.value)

    @classmethod
    def install(cls, *, customer_id: str, app_install: AppInstallEvent, account_name: str) -> BitbucketAppInstall:
        obj, created = cls.objects.update_or_create(
            customer_id=customer_id,
            defaults={
                "client_key": app_install.client_key,
                "shared_secret": app_install.shared_secret,
                "account_name": account_name,
                "account_id": app_install.account_id,
                "_app_state": AppInstallState.INSTALLED.value,
                "last_updated": utcnow(),
            },
        )
        _logger.info(f"BitbucketAppInstall.install {created=} {customer_id=} account_name={app_install.account_name}")
        return obj

    @classmethod
    def uninstall(cls, *, customer_id: str, app_uninstall: AppUninstallEvent) -> bool:
        obj = cls.get_or_none(customer_id=customer_id)
        if not obj:
            return False
        if obj.client_key != app_uninstall.client_key or obj.account_id != app_uninstall.account_id:
            _logger.warning(
                f"App install mismatch expected (client_key={obj.client_key}, account_id={obj.account_id}) got (client_key={app_uninstall.client_key}, account_id={app_uninstall.account_id})"
            )
            return False
        return obj.set_uninstall(app_uninstall.account_name, customer_id)

    def set_uninstall(self, account_name: str, customer_id: str) -> bool:
        if self.app_state != AppInstallState.INSTALLED:
            _logger.warning(
                f"App not in installed state account_name={self.account_name}, account_id={self.account_id}"
            )
            return False
        self._app_state = AppInstallState.UNINSTALLED.value
        self.account_name = account_name
        self.last_updated = utcnow()
        self.save()
        _logger.info(
            f"BitbucketAppInstall.uninstall {customer_id=} account_name={self.account_name}, account_id={self.account_id}"
        )
        return True

    def __str__(self) -> str:
        return f"BitbucketAppInstall {self.account_name} - {self.app_state.value} ({self.account_id})"
