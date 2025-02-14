# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging

from django.core.management import BaseCommand

from toolchain.packagerepo.maven.toposort_maven_artifacts import MavenArtifactSorter

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Topologically sort Maven artifacts by dependencies."

    def add_arguments(self, parser):
        parser.add_argument("--coords", required=True, help="Path to coordinates .csv file.")
        parser.add_argument("--deps", required=True, help="Path to dependencies .csv file.")
        parser.add_argument("--write-path", default=None, help="Path to write the sorted artifacts to.")

    def handle(self, *args, **options):
        sorter = MavenArtifactSorter(options["coords"], options["deps"])
        sorter.load_coordinates()
        sorter.load_deps()
        sorter.sort()
        if options["write_path"] is not None:
            sorter.write_sorted(options["write_path"])
        else:
            sorter.head()
