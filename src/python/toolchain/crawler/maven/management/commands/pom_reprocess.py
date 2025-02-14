# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.core.management.base import BaseCommand

from toolchain.crawler.maven.models import ExtractPOMInfo
from toolchain.django.db.transaction_broker import TransactionBroker
from toolchain.packagerepo.maven import artifact_locator
from toolchain.packagerepo.maven.coordinates import GAVCoordinates
from toolchain.workflow.models import WorkUnit

transaction = TransactionBroker("crawlermaven")


# Reminder that Django requires this class to be named 'Command'.
# The command name is the module name.
class Command(BaseCommand):
    help = "Force POM information extraction to re-run for given seed artifacts."

    SEED_ARTIFACTS = ["com.fasterxml.jackson.dataformat:jackson-dataformat-xml:2.8.2"]

    def handle(self, *args, **options):
        for artifact in self.SEED_ARTIFACTS:
            coords = GAVCoordinates(*artifact.split(":"))
            url = artifact_locator.ArtifactLocator().pom_url(coords)
            with transaction.atomic():
                payload, _ = ExtractPOMInfo.objects.get_or_create(url=url)
                locked_wu = WorkUnit.locked(payload.pk)
                locked_wu.rerun()
                locked_wu.save()
