# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json
import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.buildsense.search.indexes_manager import BuildsenseIndexManager

_logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Update ES type mappings"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", required=False, default=False, help="Dry run.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        mgr = BuildsenseIndexManager.for_django_settings(settings)
        new_props = self.get_new_properties(mgr)
        if not new_props:
            self.stdout.write(self.style.SUCCESS("No new properties. nothing to do."))
            return
        self.stdout.write(
            self.style.NOTICE(f"Will add {len(new_props['properties'])} type mappings. Dry run: {dry_run}")
        )
        self.stdout.write(self.style.NOTICE(json.dumps(new_props["properties"], indent=4)))
        if dry_run:
            return
        response_data = mgr.update_mapping(new_props)
        self.stdout.write(self.style.NOTICE(f"Response: {response_data!r}"))

    def get_current_mapping(self, mgr: BuildsenseIndexManager) -> dict:
        return mgr.get_current_mapping()

    def get_new_properties(self, mgr: BuildsenseIndexManager):
        index_mapping = self.get_current_mapping(mgr)
        expected_mappings = mgr.load_mappings()
        return self._find_new_props(index_mapping, expected_mappings)

    def _find_new_props(self, current: dict, expected: dict) -> dict:
        new_props = {}
        curr_props = current["properties"]
        for prop_name, prop_def in expected["properties"].items():
            if "type" in prop_def:  # field
                if prop_name in curr_props:
                    continue
                new_props[prop_name] = prop_def
            elif "properties" in prop_def:  # nested structure
                curr_def = curr_props.get(prop_name)
                if not curr_def:  # new structure
                    new_props[prop_name] = prop_def
                else:
                    new_nested_props = self._find_new_props(curr_def, prop_def)
                    if new_nested_props:
                        new_props[prop_name] = new_nested_props
            else:
                raise ToolchainAssertion(f"Unexpected prop_def for {prop_name}: {prop_def}")
        return {"properties": new_props} if new_props else {}
