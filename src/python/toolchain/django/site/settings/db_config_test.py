# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json
from unittest import mock

from toolchain.constants import ToolchainEnv
from toolchain.django.site.settings.db_config import prepare_database_dict
from toolchain.util.secret.secrets_accessor import DummySecretsAccessor


def test_prepare_database_dict_dev() -> None:
    secrets_accessor = DummySecretsAccessor.create_rotatable()
    db_secret = {
        "engine": "postgres",
        "host": "NBC",
        "port": 1222,
        "user": "cosmo",
        "password": "no-soup-4u",
        "set_role": "standup",
        "dbname": "joe",
    }
    secrets_accessor.set_secret("newman-db-users-creds", json.dumps(db_secret))
    db_dict = prepare_database_dict(
        db_names=["users"],
        toolchain_env=ToolchainEnv.DEV,  # type: ignore
        secrets_reader=secrets_accessor,
        use_remote_dev_dbs=False,
        namespace="newman",
    )
    assert db_dict == {
        "users": {
            "CONN_MAX_AGE": 3600,
            "DISABLE_SERVER_SIDE_CURSORS": False,
            "ENGINE": "django_prometheus.db.backends.postgresql",
            "HOST": "NBC",
            "NAME": "joe",
            "PASSWORD": "no-soup-4u",
            "PORT": 1222,
            "SET_ROLE": "standup",
            "USER": "cosmo",
        }
    }


@mock.patch("toolchain.django.site.settings.util.can_connect")
@mock.patch("toolchain.django.site.settings.db_config.hostname_resolves")
def test_prepare_database_dict_dev_remote_dev_dbs(mock_hostname_resolves, mock_can_connect):
    mock_can_connect.return_value = True
    mock_hostname_resolves.return_value = True
    secrets_accessor = DummySecretsAccessor.create_rotatable()
    db_secret = {
        "engine": "postgres",
        "host": "NBC",
        "port": 1222,
        "user": "cosmo",
        "password": "no-soup-4u",
        "set_role": "standup",
        "dbname": "joe",
    }
    secrets_accessor.set_secret("seinfeld-db-bubble-creds", json.dumps(db_secret))
    db_dict = prepare_database_dict(
        db_names=["bubble"],
        toolchain_env=ToolchainEnv.DEV,
        secrets_reader=secrets_accessor,
        use_remote_dev_dbs=True,
        namespace="seinfeld",
    )
    mock_can_connect.assert_called_once_with("localhost", 5435)
    mock_hostname_resolves.assert_called_once_with("seinfeld.seinfeld.svc.cluster.local")
    assert db_dict == {
        "bubble": {
            "CONN_MAX_AGE": 3600,
            "DISABLE_SERVER_SIDE_CURSORS": False,
            "ENGINE": "django_prometheus.db.backends.postgresql",
            "HOST": "localhost",
            "NAME": "joe",
            "PASSWORD": "no-soup-4u",
            "PORT": 5435,
            "SET_ROLE": "standup",
            "USER": "cosmo",
        }
    }


def test_prepare_databases_dict_dev() -> None:
    secrets_accessor = DummySecretsAccessor.create_rotatable()
    db_secret_1 = {
        "engine": "postgres",
        "host": "ovaltine",
        "port": 1222,
        "user": "mulva",
        "password": "jambalaya",
        "set_role": "standup",
        "dbname": "joe",
    }
    db_secret_2 = {
        "engine": "postgres",
        "host": "bro",
        "port": 3332,
        "user": "groom",
        "password": "sue",
        "set_role": "funnyguy",
        "dbname": "frank",
    }
    secrets_accessor.set_secret("soup-db-kramer-creds", json.dumps(db_secret_1))
    secrets_accessor.set_secret("soup-db-cosmo-creds", json.dumps(db_secret_2))
    db_dict = prepare_database_dict(
        db_names=["kramer", "cosmo"],
        toolchain_env=ToolchainEnv.DEV,  # type: ignore
        secrets_reader=secrets_accessor,
        use_remote_dev_dbs=False,
        namespace="soup",
    )
    assert db_dict == {
        "kramer": {
            "ENGINE": "django_prometheus.db.backends.postgresql",
            "NAME": "joe",
            "USER": "mulva",
            "PASSWORD": "jambalaya",
            "SET_ROLE": "standup",
            "HOST": "ovaltine",
            "PORT": 1222,
            "CONN_MAX_AGE": 3600,
            "DISABLE_SERVER_SIDE_CURSORS": False,
        },
        "cosmo": {
            "ENGINE": "django_prometheus.db.backends.postgresql",
            "NAME": "frank",
            "USER": "groom",
            "PASSWORD": "sue",
            "SET_ROLE": "funnyguy",
            "HOST": "bro",
            "PORT": 3332,
            "CONN_MAX_AGE": 3600,
            "DISABLE_SERVER_SIDE_CURSORS": False,
        },
    }


def test_prepare_database_dict_prod() -> None:
    secrets_accessor = DummySecretsAccessor.create_rotatable()
    db_secret = {
        "engine": "postgres",
        "host": "marge",
        "port": 7727,
        "user": "midsize",
        "password": "the-holding",
        "set_role": "standup",
        "dbname": "reservation",
    }
    secrets_accessor.set_secret("ford-db-cars-creds", json.dumps(db_secret))
    db_dict = prepare_database_dict(
        db_names=["cars"],
        toolchain_env=ToolchainEnv.PROD,  # type: ignore
        secrets_reader=secrets_accessor,
        use_remote_dev_dbs=False,
        namespace="ford",
    )
    assert db_dict == {
        "cars": {
            "ENGINE": "django_prometheus.db.backends.postgresql",
            # 'ENGINE': 'django_prometheus.db.backends.postgresql',
            "NAME": "reservation",
            "USER": "midsize",
            "PASSWORD": "the-holding",
            "SET_ROLE": "standup",
            "HOST": "marge",
            "PORT": 7727,
            "CONN_MAX_AGE": 3600,
            "OPTIONS": {"sslmode": "disable"},
            "DISABLE_SERVER_SIDE_CURSORS": False,
        }
    }
