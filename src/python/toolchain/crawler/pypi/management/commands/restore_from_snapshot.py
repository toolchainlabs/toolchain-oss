# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import os
import subprocess
import time
from tempfile import TemporaryDirectory

from django.conf import settings
from django.core.management.base import BaseCommand

from toolchain.aws.s3 import S3
from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.db.transaction_broker import TransactionBroker
from toolchain.packagerepo.pypi.models import Distribution, Project, Release

transaction = TransactionBroker("crawlerpypi")


class Command(BaseCommand):
    help = "Restore package repo pypi tables from a a postgres dump file."

    # See pypi_db_snapshots.py, order matters here because of foreign keys
    _TABLES = [
        "packagerepopypi_distributiondata",
        "packagerepopypi_distribution",
        "packagerepopypi_release",
        "packagerepopypi_project",
    ]
    # See pypi_db_snapshots.py
    _KEY_PREFIX = "shared/pypi_db_snapshots/"

    def add_arguments(self, parser):
        parser.add_argument("--snapshot", required=False, default=None, help="Path to snapshot file")
        parser.add_argument("--local", action="store_true", required=False, default=False, help="Restore to local DB.")

    def _write(self, style, message):
        now_str = utcnow().strftime("%H:%M:%S")
        self.stdout.write(style(f"[{now_str}] {message}"))

    def handle(self, *args, **options):
        if not settings.TOOLCHAIN_ENV.is_dev:
            raise ToolchainAssertion("This is for dev only!")
        # Reading all the settings first, making sure we have everything we need before truncating rows and downloading stuff from s3.
        db_settings = settings.DATABASES["pypi"]
        port = db_settings["PORT"]
        host = db_settings["HOST"]
        secret_name_prefix = "local" if options["local"] else settings.TOOLCHAIN_ENV.get_env_name()
        secret_name = f"{secret_name_prefix}-db-master-creds"
        master_creds = settings.SECRETS_READER.get_json_secret(secret_name)
        if not master_creds:
            raise ToolchainAssertion(f"Could not read secret {secret_name} via {settings.SECRETS_READER}")
        master_user = master_creds["user"]
        master_password = master_creds["password"]
        with TemporaryDirectory() as tmpdir:
            dump_file = self._get_dump_file(options, tmpdir)
            self._clear_objects()
            start = time.time()
            self._restore_snapshot(
                dump_file=dump_file, host=host, port=port, user=master_user, password=master_password
            )
        self.print_stats(int(time.time() - start))

    def print_stats(self, latency):
        projects = Project.objects.count()
        releases = Release.objects.count()
        distributions = Distribution.objects.count()
        self._write(
            self.style.SUCCESS,
            f"Restore completed {latency} seconds. Projects: {projects:,} Releases: {releases:,} Distributions: {distributions:,} ",
        )

    def _get_dump_file(self, options, tmpdir):
        dump_file = options["snapshot"]
        if dump_file:
            return dump_file
        s3 = S3()
        bucket = settings.WEBRESOURCE_BUCKET
        keys = sorted(
            s3.key_metadata_with_prefix(bucket, self._KEY_PREFIX), key=lambda md: md["LastModified"], reverse=True
        )
        if not keys:
            raise ToolchainAssertion(f"No DB Snapshot dumps found under s3://{bucket}/{self._KEY_PREFIX}")
        latest = keys[0]
        dump_file = os.path.join(tmpdir, "pypi_db.dump")
        key = latest["Key"]
        size_mb = int(latest["Size"] / 1024 / 1024)
        self._write(self.style.NOTICE, f"Downloading dump file from s3://{bucket}/{key} {size_mb:,}mb")
        s3.download_file(bucket=bucket, key=key, path=dump_file)
        return dump_file

    def _clear_objects(self):
        self._write(self.style.NOTICE, "Deleting rows from package repo tables.")
        sql_commands = [f'TRUNCATE TABLE "{table}" CASCADE' for table in self._TABLES]
        with transaction.atomic(), transaction.connection.cursor() as cursor:
            for cmd in sql_commands:
                cursor.execute(cmd)

    def _restore_snapshot(self, dump_file, host, port, user, password):
        self._write(self.style.NOTICE, f"Restoring tables to {host}:{port} from {dump_file}")
        cmd = [
            "pg_restore",
            "-h",
            host,
            "-p",
            str(port),
            "-U",
            user,
            "--role=pypi_owner",
            "--disable-triggers",
            "-d",
            "pypi",
            "--superuser",
            user,
            "--no-owner",
            "--data-only",
            dump_file,
        ]
        process_env = os.environ.copy()
        process_env["PGPASSWORD"] = password
        subprocess.run(cmd, check=True, env=process_env)
